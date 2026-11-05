"""窓ごとに、スペクトルの上位のピーク（周波数と dBFS 換算の振幅）を出す。
   specpeaks.py WAV start:end [start:end ...]
"""
import sys
import wave
import numpy as np

path = sys.argv[1]
windows = [tuple(float(v) for v in s.split(':')) for s in sys.argv[2:]]
with wave.open(path, 'rb') as w:
    ch, rate, n = w.getnchannels(), w.getframerate(), w.getnframes()
    a = np.frombuffer(w.readframes(n), dtype='<i2').reshape(-1, ch).astype(np.float64) / 32768.0

nfft = 1 << 16
win = np.hanning(nfft)
cg = win.sum() / 2  # 正弦波の振幅を出すための窓の補正
for (t0, t1) in windows:
    for c in range(ch):
        seg = a[int(t0 * rate):int(t1 * rate), c]
        acc = None
        cnt = 0
        for i in range(0, len(seg) - nfft + 1, nfft // 2):
            f = np.abs(np.fft.rfft(seg[i:i + nfft] * win)) / cg
            acc = f ** 2 if acc is None else acc + f ** 2
            cnt += 1
        amp = np.sqrt(acc / cnt)
        df = rate / nfft
        lo = int(50 / df)
        idx = [i for i in np.argsort(amp[lo:])[::-1][:400] + lo]
        picked = []
        for i in idx:
            if all(abs(i - j) > int(30 / df) for j in picked):
                picked.append(i)
            if len(picked) == 6:
                break
        print('%5.1f-%5.1f s ch%d: ' % (t0, t1, c) + '  '.join(
            '%.0fHz %.1fdBFS' % (i * df, 20 * np.log10(amp[i] + 1e-12)) for i in picked))
