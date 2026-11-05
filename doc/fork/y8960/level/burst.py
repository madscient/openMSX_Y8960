"""振幅が大きい部分（バースト）の開始・終了の時刻、長さ、主なスペクトルのピークを出す。
   burst.py WAV marks.txt [threshold_dbfs]
"""
import sys
import wave
import numpy as np

path, marks_path = sys.argv[1], sys.argv[2]
thr = 10 ** ((float(sys.argv[3]) if len(sys.argv) > 3 else -35.0) / 20)

with wave.open(path, 'rb') as w:
    ch, rate, n = w.getnchannels(), w.getframerate(), w.getnframes()
    a = np.frombuffer(w.readframes(n), dtype='<i2').reshape(-1, ch).astype(np.float64) / 32768.0
x = a[:, 0]

marks = []
with open(marks_path, encoding='utf-8-sig') as f:
    for line in f:
        p = line.split()
        if len(p) == 2:
            try:
                marks.append((float(p[0]), p[1]))
            except ValueError:
                pass
print('marks:', ', '.join('%.2f %s' % m for m in marks))

hop = int(rate * 0.01)
env = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2)) for i in range(0, n - hop, hop)])
on = env > thr
i = 0
events = []
while i < len(on):
    if on[i]:
        j = i
        while j < len(on) and (on[j] or (j + 5 < len(on) and on[j:j + 5].any())):
            j += 1
        events.append((i * 0.01, j * 0.01))
        i = j
    else:
        i += 1
for (t0, t1) in events:
    seg = x[int(t0 * rate):int(t1 * rate)]
    if len(seg) < 256:
        pk = 'short'
    else:
        nfft = 1 << int(np.floor(np.log2(len(seg))))
        sp = np.abs(np.fft.rfft(seg[:nfft] * np.hanning(nfft)))
        k = int(np.argmax(sp[int(50 * nfft / rate):])) + int(50 * nfft / rate)
        pk = '%.0f Hz' % (k * rate / nfft)
    near = [m for m in marks if m[0] <= t0]
    rel = ('%.2f s after %s' % (t0 - near[-1][0], near[-1][1])) if near else 'before the first mark'
    print('burst %6.2f - %6.2f s (%.2f s)  peak %.1f dBFS  main %s   %s' % (
        t0, t1, t1 - t0, 20 * np.log10(np.max(np.abs(seg)) + 1e-12), pk, rel))
