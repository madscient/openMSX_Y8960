"""mkfbd.py のパッチを鳴らした録音を測り、FB の倍音の形が fbmodel.py のどの仮説に合うかを判定する。

    py anafbd.py take1.wav [...]

立ち上がりと位置合わせは anaws.py と同じ（24 打はすべて鳴る）。打ごとに [立ち上がり + 100ms, + 700ms] を取り、
Blackman-Harris 窓の DFT で k × f0（k = 1-8）の大きさを測る。f0 は最初の打（MULT 1、FB0）の 440Hz 付近の山から取る。

  R_k = CAL の MULT k の打の大きさ − MULT 1 の打の大きさ（録音の経路の周波数特性。チップの出力は MULT によらず同じ）
  L_k = 打の H_k − H_1 − R_k（k = 2-8）
  N_k = 最初の打の前の無音での k × f0 の雑音 − 打の H_1 − R_k
  F_k = max(同じ TL の FB0 の打の L_k, N_k, -60dB)  （純音でも出る倍音より下は測れない。-60dB の下限は下の注）
  P_k = 仮説のモデルの H_k − H_1

判定の基準（録音を見る前に決めた）。FB 1-6 の TL0・TL12 の 12 打それぞれで:
  K = { k : どれかの仮説の P_k > F_k + 6dB、または L_k > F_k + 6dB }
  d = K の上での (max(L_k, F_k) − max(P_k, F_k)) の二乗平均平方根
  d <= 3dB なら、その打で仮説は「合う」。d >= 6dB なら「外れる」
回が有効なのは、24 打の立ち上がりがすべて見つかり、クリップが無く、最初と最後の CAL MULT 1 の f0 の差が 0.05Hz 以下、
大きさの差が 0.5dB 以下のとき。仮説ごとに、有効な回のすべての打で「合う」なら「合う」、有効な回のどれでも 1 打以上
「外れる」なら「外れる」、ほかは「決まらない」
FB7 は表示だけで判定に使わない。TL0 の FB7 は、モデルでも区間の取り方で H5 が 5dB ほど動く（合成の録音で見た）。
-60dB の下限: 440Hz の位相の増分 4640 では出力が 16384 サンプルの周期になり、倍音の脇に 3.03Hz おきの量子化の線が立つ。
0.6 秒の窓の主葉（±6.7Hz）はそれを分けられず、-70dB より下の倍音は窓の置き方で値が動く（合成の録音で、同じモデルから
作った音でも予測と 8dB ずれた）
"""
import sys

import numpy as np

import anaws
import fbmodel
from mkfbd import SEQ

WIN = (0.100, 0.700)
KMAX = 8
FIT, MISS, MARGIN, LOWEST = 3.0, 6.0, 6.0, -60.0
JUDGED = range(1, 7)


def find_f0(seg, rate, f=440.0):
    for span, step in ((5.0, 0.1), (0.15, 0.002)):
        grid = np.arange(f - span, f + span + step / 2, step)
        f = float(grid[int(np.argmax([fbmodel.amp(seg, rate, g) for g in grid]))])
    return f


def onsets_of(path):
    m, rate, clip = anaws.read(path)
    db = anaws.frames_db(m, rate)
    n = len(SEQ)
    floor0 = np.median(db[: int(1.0 / anaws.FRAME)])
    onsets, _ = anaws.align(db, floor0 + 20, n)
    a, b = int((onsets[0] - 0.6) / anaws.FRAME), int((onsets[0] - 0.1) / anaws.FRAME)
    floor = max(floor0, float(np.median(db[a:b])))
    onsets, nfound = anaws.align(db, floor + 20, n)
    return m, rate, clip, floor, onsets, nfound


def db(x):
    return 20 * np.log10(np.maximum(x, 1e-12))


def take(path, pred):
    m, rate, clip, floor, onsets, nfound = onsets_of(path)
    segs = [m[int((t + WIN[0]) * rate):int((t + WIN[1]) * rate)] for t in onsets]
    f0a, f0b = find_f0(segs[0], rate), find_f0(segs[-1], rate)
    f0 = f0a
    q = int((onsets[0] - 0.65) * rate)
    quiet = m[q:q + len(segs[0])]
    noise = np.array([np.sqrt(np.mean([fbmodel.amp(quiet, rate, k * f0 + d) ** 2 for d in range(-30, 31, 10)]))
                      for k in range(1, KMAX + 1)])
    H = [np.array([fbmodel.amp(s, rate, k * f0) for k in range(1, KMAX + 1)]) for s in segs]
    cal = {}
    for (name, mult, fb, tl), s in zip(SEQ, segs):
        if name == 'CAL' and mult not in cal:
            cal[mult] = fbmodel.amp(s, rate, mult * f0)
    R = db(np.array([cal[k] for k in range(1, KMAX + 1)])) - db(cal[1])
    last_cal = fbmodel.amp(segs[-1], rate, f0)
    steps = np.diff(onsets)
    valid = nfound == len(SEQ) - 1 and clip == 0 and abs(f0a - f0b) <= 0.05 and abs(db(last_cal) - db(cal[1])) <= 0.5
    print(f'{path}: {rate} Hz, clipped {clip}, floor {floor:.1f} dBFS, onsets found {nfound}/{len(SEQ) - 1}, '
          f'spacing {steps.min():.3f}-{steps.max():.3f} s')
    print(f'  f0 {f0a:.3f} / {f0b:.3f} Hz, CAL MULT1 {db(cal[1]):.2f} / {db(last_cal):.2f} dB, '
          f'R(k=2..8) ' + ' '.join(f'{v:+.1f}' for v in R[1:]))
    print('  take valid:', valid)
    L = {}
    N = {}
    for (name, mult, fb, tl), h in zip(SEQ, H):
        if name == 'CAL' and mult != 1:
            continue
        key = (fb, tl)
        if key in L:
            continue
        L[key] = db(h[1:]) - db(h[0]) - R[1:]
        N[key] = db(noise[1:]) - db(h[0]) - R[1:]
    rows = {}
    for tl in (0, 12):
        print(f'  TL{tl}  FB0 L(k=2..8) ' + ' '.join(f'{v:6.1f}' for v in L[(0, tl)])
              + '   noise ' + ' '.join(f'{v:6.1f}' for v in N[(0, tl)]))
        for fb in range(1, 8):
            Lk = L[(fb, tl)]
            F = np.maximum(np.maximum(L[(0, tl)], N[(fb, tl)]), LOWEST)
            P = {h: pred[(h, fb, tl)] for h in fbmodel.HYP}
            use = (Lk > F + MARGIN)
            for h in P:
                use |= P[h] > F + MARGIN
            d = {}
            for h in P:
                d[h] = (float(np.sqrt(np.mean((np.maximum(Lk, F)[use] - np.maximum(P[h], F)[use]) ** 2)))
                        if use.any() else float('nan'))
            if fb in JUDGED:
                rows[(fb, tl)] = d
            print(f'  TL{tl:<2d} FB{fb} L ' + ' '.join(f'{v:6.1f}' for v in Lk)
                  + '  K=' + ''.join(str(k + 2) for k in np.nonzero(use)[0])
                  + '  d ' + ' '.join(f'{h}:{d[h]:5.1f}' for h in P))
    return valid, rows


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    anaws.WS_SEQ = list(range(len(SEQ)))
    anaws.INSTR = ['x']
    pred = fbmodel.predict(KMAX)
    print('model H_k/H_1 (k=2..8):')
    for tl in (0, 12):
        for fb in range(1, 8):
            print(f'  TL{tl:<2d} FB{fb} ' + '  '.join(f'{h}:' + ' '.join(f'{v:5.0f}' for v in pred[(h, fb, tl)])
                                               for h in ('real', 'y8960', 'pr16')))
    takes = []
    for path in sys.argv[1:]:
        valid, rows = take(path, pred)
        if valid:
            takes.append(rows)
    print(f'valid takes: {len(takes)} of {len(sys.argv) - 1}')
    for h in fbmodel.HYP:
        fit_all = all(r[key][h] <= FIT for r in takes for key in r if not np.isnan(r[key][h]))
        miss_each = all(any(r[key][h] >= MISS for key in r) for r in takes)
        nfit = [sum(r[key][h] <= FIT for key in r) for r in takes]
        nmiss = [sum(r[key][h] >= MISS for key in r) for r in takes]
        v = 'undecided'
        if takes and fit_all:
            v = 'fits'
        elif takes and miss_each:
            v = 'misses'
        print(f'  {h:6s} fit {nfit} miss {nmiss} of {2 * len(JUDGED)} per take -> {v}')


if __name__ == '__main__':
    main()
