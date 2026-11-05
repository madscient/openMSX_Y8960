"""pan9.txt を鳴らした録音から、OPL2 の F6h-FEh がどの ch に掛かったかを判定する。

    py pan9-levels.py REC.wav [REC.wav ...]      実機の録音も openMSX の録音も同じように測る

区間の切り出しは tone-levels.py と同じ。区間ごとに 9ch の周波数（公称値の ±2% で最大のピーク）の
L と R の振幅を測り、L - R が 20dB を超えた ch を「左に寄った」とする。
期待は仕様（xlsx）どおり、F5h+n が ch n。区間ごとに寄った ch の集合が期待と一致するかを出す。
"""

import argparse
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('tone_levels', HERE / 'tone-levels.py')
tl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tl)

FNUM = [330 + 40 * i for i in range(9)]
FREQ = [f * 49716 / 32768 for f in FNUM]
MOVED = 20.0


def expected(label):
    if label == 'all-center':
        return set()
    if label == 'all-left':
        return set(range(1, 10))
    return {int(label.split('-')[0], 16) - 0xF5}


def levels(x, rate, a, b):
    t = int(tl.TRIM * rate)
    y = x[a + t:b - t]
    n = len(y)
    w = np.hanning(n)
    freqs = np.fft.rfftfreq(n, 1.0 / rate)
    p = [np.abs(np.fft.rfft((y[:, c] - y[:, c].mean()) * w)) ** 2 for c in range(2)]
    out = []
    for f in FREQ:
        band = (freqs >= f * 0.98) & (freqs <= f * 1.02)
        k = int(np.argmax(np.where(band, p[0] + p[1], 0)))
        lo, hi = max(k - tl.LOBE, 0), k + tl.LOBE + 1
        amp = [2.0 * math.sqrt(q[lo:hi].sum() / (n * (w ** 2).sum())) for q in p]
        out.append((freqs[k], amp[0], amp[1]))
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('wav', nargs='+')
    ap.add_argument('--seq', default=HERE / 'pan9.txt')
    a = ap.parse_args()
    names = tl.labels(a.seq)
    bad = 0
    for path in a.wav:
        x, rate = tl.read_wav(path)
        segs, th = tl.segments(x, rate)
        print(f'{path}: {rate}Hz、区間 {len(segs)} 個（閾値 {tl.db(th):.1f} dBFS）')
        if len(segs) != len(names):
            for s, e in segs:
                print(f'  {s / rate:7.2f}-{e / rate:7.2f} 秒')
            sys.exit(f'区間の数が mark の数 {len(names)} と合わない')
        print('  L - R（dB）' + ' ' * 9 + ''.join(f'   ch{c:<3d}' for c in range(1, 10)) + '   寄った ch')
        for name, (s, e) in zip(names, segs):
            lv = levels(x, rate, s, e)
            d = [tl.db(l) - tl.db(r) for _, l, r in lv]
            moved = {c + 1 for c, v in enumerate(d) if v > MOVED}
            ok = moved == expected(name)
            bad += not ok
            print(f'  {name:12s} {s / rate:6.1f} 秒 ' + ''.join(f'{v:+8.1f}' for v in d)
                  + f'   {",".join(map(str, sorted(moved))) or "-":18s} {"OK" if ok else "NG"}')
        print('  周波数（Hz、全部中央の区間）: '
              + ' '.join(f'{f:.1f}' for f, _, _ in levels(x, rate, *segs[0])))
    print('\n全区間が仕様どおり' if bad == 0 else f'\n仕様と違う区間が {bad} 個')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
