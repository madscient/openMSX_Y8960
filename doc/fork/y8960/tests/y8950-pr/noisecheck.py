"""gen_noise.py の音列をチャンネルごとに録ったものから、HH（ch13）と SD（ch11）の雑音のビットを読み取り、雑音の発生器の模型と照合する。
    py noisecheck.py <dir> <rtl|nuked>

模型（1 サンプルに 18 歩）
  rtl  : Y8960 の RTL（JTOPL）。左に送る 23 ビット、帰還（＝出力）は bit22^bit9^bit8^bit0。HH は 14 歩目、SD は 17 歩目の出力を読む
  nuked: Nuked-OPL3。右に送る 23 ビット、帰還は bit0^bit14 を bit22 へ。HH はサンプルの頭の状態の bit13、SD は bit16 を読む
読み取ったビットはどれも、未知の 23 ビットの状態の一次式（GF(2)）になる。最初の 200 個で状態を解き、その状態から残りのすべてを予測して、
外れの数を出す。模型が違えば、解けないか、外れが約半分になる。
"""
import sys
import wave
from pathlib import Path

import numpy as np

MASK = (1 << 23) - 1


def load(p):
    with wave.open(str(p), 'rb') as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.int64)
        if w.getnchannels() == 2:
            a = a[0::2]
    return a


def extract(d):
    hh, sd = load(d / 'ch13.wav'), load(d / 'ch11.wav')
    on = np.nonzero(hh > 0)[0]
    a, b = on[0] + 10, on[-1] - 200   # 立ち上がりの直後と、リリースの減衰を除く
    h, s = hh[a:b], sd[a:b]
    hmax, smax = h.max(), s.max()
    hb = (h > 0.6 * hmax).astype(int)          # 0.957 か 0.316
    sb = (s > 0.5 * smax).astype(int)          # 最大か 0
    bad = int(((s > 0.1 * smax) & (s < 0.9 * smax)).sum() + ((h < 0.2 * hmax)).sum())
    # 飽和すると HH の 2 つの大きさの比が縮み、しきい値で読み分けられなくなる
    bad += int((np.abs(h) >= 32767).sum() + (np.abs(s) >= 32767).sum())
    return hb, sb, bad


def functionals(model, off, n):
    """k = 0..n-1 のサンプルの観測が、頭の状態 s のどの線形の組み合わせかを、ビットマスクの列で返す。"""
    if model == 'rtl':
        step = lambda r: (r >> 1) ^ ((1 << 22 | 1 << 9 | 1 << 8 | 1) if r & 1 else 0)
        c = 1 << 22 | 1 << 9 | 1 << 8 | 1
    else:
        step = lambda r: ((r << 1) & MASK) ^ ((1 | 1 << 14) if (r >> 22) & 1 else 0)
        c = 1 << off
        off = 0
    r = c
    for _ in range(off):
        r = step(r)
    out = []
    for _ in range(n):
        out.append(r)
        for _ in range(18):
            r = step(r)
    return out


def solve(rows, bits):
    piv = {}
    for r, b in zip(rows, bits):
        for p in sorted(piv, reverse=True):
            if (r >> p) & 1:
                r ^= piv[p][0]
                b ^= piv[p][1]
        if r == 0:
            if b:
                return None   # 矛盾
            continue
        p = r.bit_length() - 1
        for q in list(piv):
            if (piv[q][0] >> p) & 1:
                piv[q] = (piv[q][0] ^ r, piv[q][1] ^ b)
        piv[p] = (r, b)
    if len(piv) < 23:
        return None
    s = 0
    for p, (r, b) in piv.items():
        if b:
            s |= 1 << p
    return s


def main():
    d, model = Path(sys.argv[1]), sys.argv[2]
    hb, sb, bad = extract(d)
    n = len(hb)
    offs = {'rtl': (14, 17), 'nuked': (13, 16)}[model]
    fh = functionals(model, offs[0], n)
    fs = functionals(model, offs[1], n)
    rows = [x for pair in zip(fh[:100], fs[:100]) for x in pair]
    bits = [int(x) for pair in zip(hb[:100], sb[:100]) for x in pair]
    s = solve(rows, bits)
    print(f'{d}: {n} samples, {bad} samples between the levels')
    if s is None:
        print(f'  model {model}: no state fits the first 200 bits -> NO MATCH')
        return
    par = lambda x: bin(x & s).count('1') & 1
    mh = sum(par(f) != b for f, b in zip(fh, hb))
    ms = sum(par(f) != b for f, b in zip(fs, sb))
    verdict = 'MATCH' if mh == 0 and ms == 0 else 'NO MATCH'
    print(f'  model {model}: state {s:06x}, mispredicted HH {mh} of {n}, SD {ms} of {n} -> {verdict}')


if __name__ == '__main__':
    main()
