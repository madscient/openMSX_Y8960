import sys
import wave
import numpy as np

path, marks_path = sys.argv[1], sys.argv[2]
win = 0.5

with wave.open(path, 'rb') as w:
    ch, rate, n = w.getnchannels(), w.getframerate(), w.getnframes()
    a = np.frombuffer(w.readframes(n), dtype='<i2').reshape(-1, ch).astype(np.float64) / 32768.0

marks = []
with open(marks_path, encoding='utf-8-sig') as f:
    for line in f:
        parts = line.split()
        if len(parts) == 2:
            try:
                marks.append((float(parts[0]), parts[1]))
            except ValueError:
                pass
print('marks (s from recording start):', ', '.join('%.1f %s' % m for m in marks))

step = int(rate * win)
names = {int(t // win): nm for t, nm in marks}
print('t(s)   L rms dBFS   R rms dBFS   L peak dBFS')
for i in range(0, n // step):
    seg = a[i * step:(i + 1) * step]
    rms = np.sqrt(np.mean(seg * seg, axis=0))
    pk = np.max(np.abs(seg), axis=0)
    tag = names.get(i, '')
    print('%5.1f   %8.1f     %8.1f     %8.1f   %s' % (
        i * win, 20 * np.log10(rms[0] + 1e-12), 20 * np.log10(rms[1] + 1e-12),
        20 * np.log10(pk[0] + 1e-12), tag))
