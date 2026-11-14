"""録音の抜き出しを 1 本の WAV につなぐ。間に 1.5 秒の無音を挟む。人が聞き比べるためのもの。

    py listen.py out.wav file1.wav:開始秒:終了秒 file2.wav:開始秒:終了秒 ...
"""
import sys
import wave

import numpy as np

out = sys.argv[1]
parts = []
rate = None
for spec in sys.argv[2:]:
    path, a, b = spec.rsplit(':', 2)
    with wave.open(path, 'rb') as w:
        r, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1, ch)
    rate = rate or r
    assert r == rate
    parts.append(x[int(float(a) * r):int(float(b) * r)])
    parts.append(np.zeros((int(1.5 * rate), ch), dtype='<i2'))
y = np.concatenate(parts[:-1])
with wave.open(out, 'wb') as w:
    w.setnchannels(y.shape[1])
    w.setsampwidth(2)
    w.setframerate(rate)
    w.writeframes(y.tobytes())
print(out, f'{len(y) / rate:.1f} s')
