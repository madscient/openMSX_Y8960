"""chrec.tcl の出力 2 組をチャンネルごとに比べる。

    py cmpdir.py <A> <B> [--scale S]

チャンネルごとに、バイト一致か、違う場合は差の最大値と、差が出た区間（A の log.txt の mark で名前を付ける）を出す。
各チャンネルの最大振幅も出す（無音どうしの一致を見分けるため）。--scale を付けると B を S 倍とみなし（B ≈ S × A）、
16 ビットの丸めを許して比べる。ステレオの WAV は左だけを使う。
"""
import sys
import wave
from pathlib import Path

import numpy as np


def load(p):
    with wave.open(str(p), 'rb') as w:
        n = w.getnframes()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        rate = w.getframerate()
        raw = w.readframes(n)
    dt = {2: np.int16, 4: np.int32}[sw]
    a = np.frombuffer(raw, dtype=dt).astype(np.int64)
    if ch == 2:
        a = a[0::2]
    return a, rate


def marks(d):
    out = []
    p = Path(d) / 'log.txt'
    if p.exists():
        for line in p.read_text(encoding='utf-8').splitlines():
            parts = line.split()
            if len(parts) == 2:
                try:
                    out.append((float(parts[0]), parts[1]))
                except ValueError:
                    pass
    return out


def label_at(ms, t):
    name = '(start)'
    for tt, nm in ms:
        if tt <= t:
            name = nm
    return name


def main():
    a_dir, b_dir = Path(sys.argv[1]), Path(sys.argv[2])
    scale = None
    if '--scale' in sys.argv:
        scale = float(sys.argv[sys.argv.index('--scale') + 1])
    ms = marks(a_dir)
    same_all = True
    for i in range(1, 16):
        pa, pb = a_dir / f'ch{i}.wav', b_dir / f'ch{i}.wav'
        if not pa.exists() or not pb.exists():
            print(f'ch{i}: missing ({pa.exists()}, {pb.exists()})')
            same_all = False
            continue
        a, rate = load(pa)
        b, _ = load(pb)
        peak = int(max(np.abs(a).max(initial=0), np.abs(b).max(initial=0)))
        if scale is None and pa.read_bytes() == pb.read_bytes():
            print(f'ch{i}: identical bytes (peak {peak})')
            continue
        n = min(len(a), len(b))
        if scale is None:
            d = np.abs(a[:n] - b[:n])
            tol = 0
        else:
            d = np.abs(np.round(a[:n] * scale) - b[:n])
            tol = 1
        bad = np.nonzero(d > tol)[0]
        if len(bad) == 0:
            print(f'ch{i}: equal within {tol} (len {len(a)} vs {len(b)}, peak {peak})')
            continue
        same_all = False
        regions = {}
        for k in bad:
            nm = label_at(ms, k / rate)
            regions[nm] = regions.get(nm, 0) + 1
        print(f'ch{i}: DIFF max {int(d.max())} at {bad[0] / rate:.4f}s, {len(bad)} samples, peak {peak}, len {len(a)} vs {len(b)}')
        print('       by mark: ' + ', '.join(f'{k}={v}' for k, v in regions.items()))
    print('ALL SAME' if same_all else 'SOME DIFFER')


main()
