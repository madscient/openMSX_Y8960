"""狭い帯域のピークが、周りの雑音の中央値より何 dB 高いかを、窓ごとに出す。
   tonepeak.py WAV quiet_start quiet_end [--inject dBFS] [--freq HZ] start:end ...
"""
import sys
import wave
import numpy as np

args = sys.argv[1:]
path = args.pop(0)
inject = None
freq = 1000.0
if '--inject' in args:
    i = args.index('--inject')
    inject = float(args[i + 1])
    del args[i:i + 2]
if '--freq' in args:
    i = args.index('--freq')
    freq = float(args[i + 1])
    del args[i:i + 2]
windows = [tuple(float(v) for v in s.split(':')) for s in args]

with wave.open(path, 'rb') as w:
    ch, rate, n = w.getnchannels(), w.getframerate(), w.getnframes()
    a = np.frombuffer(w.readframes(n), dtype='<i2').reshape(-1, ch).astype(np.float64) / 32768.0

if inject is not None:
    # 物差しの点検: 2 つ目以降の窓の L と R の両方に正弦波を足して、拾えるかを見る
    amp = 10 ** (inject / 20)
    for (t0, t1) in windows[1:]:
        s0, s1 = int(t0 * rate), int(t1 * rate)
        t = np.arange(s1 - s0) / rate
        for c in range(ch):
            a[s0:s1, c] += amp * np.sin(2 * np.pi * freq * t)


def peak_over_median(x, t0, t1):
    seg = x[int(t0 * rate):int(t1 * rate)]
    nfft = 1 << 16
    if len(seg) < nfft:
        nfft = 1 << int(np.floor(np.log2(len(seg))))
    win = np.hanning(nfft)
    acc = None
    cnt = 0
    for i in range(0, len(seg) - nfft + 1, nfft // 2):
        p = np.abs(np.fft.rfft(seg[i:i + nfft] * win)) ** 2
        acc = p if acc is None else acc + p
        cnt += 1
    psd = acc / cnt
    df = rate / nfft
    near = slice(int((freq - 20) / df), int((freq + 20) / df) + 1)
    around = np.r_[int((freq - 300) / df):int((freq - 40) / df), int((freq + 40) / df):int((freq + 300) / df)]
    peak = psd[near].max()
    med = np.median(psd[around])
    return 10 * np.log10(peak / med), 10 * np.log10(peak), cnt


print('freq %.0f Hz, inject %s' % (freq, 'none' if inject is None else '%.1f dBFS' % inject))
for (t0, t1) in windows:
    row = []
    for c in range(ch):
        r, pk, cnt = peak_over_median(a[:, c], t0, t1)
        row.append('ch%d peak/median %5.1f dB (frames %d)' % (c, r, cnt))
    print('%5.1f-%5.1f s   %s' % (t0, t1, '   '.join(row)))
