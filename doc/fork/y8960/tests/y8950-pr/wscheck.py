"""gen_ws.py の音列を chrec.tcl で録ったものを、mark ごとにその音のチャンネルの最小・最大で見る。
    py wscheck.py <dir> <y8960|y8950>
期待: y8960 は w1 で負の値が無く、w0 と off には在る。y8950 はどれにも在る。"""
import sys
import wave
from pathlib import Path

import numpy as np

CH = {'BD': 10, 'SD': 11, 'CY': 12, 'HH': 13, 'TOM': 14}
d = Path(sys.argv[1])
kind = sys.argv[2]
data = {}
for name, c in CH.items():
    with wave.open(str(d / f'ch{c}.wav'), 'rb') as w:
        rate = w.getframerate()
        data[name] = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.int64)
ok = True
for line in open(d / 'log.txt', encoding='utf-8'):
    parts = line.split()
    if len(parts) != 2:
        continue
    t, label = float(parts[0]), parts[1]
    case, name = label.split('-')
    x = data[name][int((t + 0.005) * rate):int((t + 0.240) * rate)]
    neg = int((x < 0).sum())
    expect_neg = not (kind == 'y8960' and case == 'w1')
    good = (neg > 0) == expect_neg and np.abs(x).max() > 100
    ok &= good
    print(f'{label:8s} min {x.min():7d} max {x.max():7d} negatives {neg:6d}  expect {"some" if expect_neg else "none"}  {"OK" if good else "NG"}')
print('RESULT', 'OK' if ok else 'NG')
