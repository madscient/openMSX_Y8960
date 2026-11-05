import sys
import wave
import numpy as np

for p in sys.argv[1:]:
    with wave.open(p, 'rb') as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    a = np.frombuffer(raw, dtype='<i2').reshape(-1, ch).astype(np.float64) / 32768.0
    print('%s: %d ch, %d Hz, %.2f s' % (p, ch, rate, n / rate))
    for c in range(ch):
        x = a[:, c]
        rms = np.sqrt(np.mean(x * x))
        pk = np.max(np.abs(x))
        dc = np.mean(x)
        print('  ch%d rms %.1f dBFS  peak %.1f dBFS  dc %.5f' % (
            c, 20 * np.log10(rms + 1e-12), 20 * np.log10(pk + 1e-12), dc))
