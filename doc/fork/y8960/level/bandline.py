"""狭い帯域の振幅 (dBFS) を時間順に出す。鳴っている間と止まっている間の差を見る。
   bandline.py WAV marks.txt lo_hz hi_hz [step_s]
"""
import sys
import wave
import numpy as np

path, marks_path = sys.argv[1], sys.argv[2]
lo_hz, hi_hz = float(sys.argv[3]), float(sys.argv[4])
step = float(sys.argv[5]) if len(sys.argv) > 5 else 0.25

with wave.open(path, 'rb') as w:
    ch, rate, n = w.getnchannels(), w.getframerate(), w.getnframes()
    a = np.frombuffer(w.readframes(n), dtype='<i2').reshape(-1, ch).astype(np.float64) / 32768.0
x = a[:, 0]

marks = {}
with open(marks_path, encoding='utf-8-sig') as f:
    for line in f:
        p = line.split()
        if len(p) == 2:
            try:
                marks[int(float(p[0]) // step)] = p[1]
            except ValueError:
                pass

nfft = int(rate * step)
win = np.hanning(nfft)
cg = win.sum() / 2
df = rate / nfft
b0, b1 = int(lo_hz / df), int(hi_hz / df) + 1
print('band %.0f-%.0f Hz, window %.2f s (bin %.1f Hz)' % (lo_hz, hi_hz, step, df))
for i in range(0, n // nfft):
    seg = x[i * nfft:(i + 1) * nfft] * win
    sp = np.abs(np.fft.rfft(seg)) / cg
    e = np.sqrt(np.sum(sp[b0:b1] ** 2))
    print('%6.2f s  %7.1f dBFS  %s' % (i * step, 20 * np.log10(e + 1e-12), marks.get(i, '')))
