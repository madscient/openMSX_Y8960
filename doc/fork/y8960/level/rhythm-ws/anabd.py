"""mkbd.py のパッチを鳴らした録音を測り、リズム時の BD が C6h の CON で FM を止めるか、変調器を出力に足すかを判定する。

    py anabd.py take1.wav [...]

立ち上がりと位置合わせは anaws.py と同じ（16 打はすべて鳴る）。打ごとに [立ち上がり + 100ms, + 700ms] を取り、
Blackman-Harris 窓の DFT で k × f（k = 1-8）の大きさ P_k を測る（fbmodel.amp）。f は CTL CON1 の打のキャリア（2f）の山の半分。
雑音 N_k は、最初の打の前の無音の同じ長さで、k × f の前後 ±30Hz の 7 点の二乗平均。

  T   = Σ P_k^2                       （k = 1-8）
  FM  = 10 log((P_1^2 + P_5^2) / T)   （キャリアに FM が掛かると立つ線。3f の倍数でもキャリアの倍音でもない）
  MOD = 10 log(P_3^2 / T)             （変調器が出力に混ざると立つ線）
  NFM・NMOD は、P を N に替えて同じ T で割ったもの

判定の基準（録音を見る前に決めた）。打ごとに:
  FM  >= -15dB なら「FM あり」。FM <= -35dB かつ NFM <= -41dB なら「FM なし」。ほかは「決まらない」
  MOD >= -25dB なら「変調器あり」。MOD <= -40dB かつ NMOD <= -46dB なら「変調器なし」。ほかは「決まらない」
  組み合わせで、なし・なし = carrier only、あり・なし = FM、なし・あり = carrier + modulator、あり・あり = FM + modulator
回が有効なのは、16 打の立ち上がりがすべて見つかり、クリップが無く、最初と最後の CTL CON1 の 2f の差が 0.1Hz 以下で、
対照の 8 打がすべて期待どおり（CTL CON0 は FM、CTL CON1 は carrier + modulator）のとき。
BD CON0・BD CON1 は、回の中の 4 打がすべて同じならそれ、ほかは「決まらない」。有効な回がすべて同じなら、それを結果とする。
"""
import sys

import numpy as np

import anaws
import fbmodel
from mkbd import SEQ, BLOCK, FNUM

WIN = (0.100, 0.700)
KMAX = 8
F_NOM = FNUM * 3579545 / 72 * 2 ** (BLOCK - 1) / 2 ** 19
EXPECT_CTL = {0: 'FM', 1: 'carrier + modulator'}
NAMES = {(False, False): 'carrier only', (True, False): 'FM', (False, True): 'carrier + modulator',
         (True, True): 'FM + modulator'}


def find_peak(seg, rate, f):
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


def l10(x):
    return 10 * np.log10(max(x, 1e-30))


def verdict(fm, mod, nfm, nmod):
    a = True if fm >= -15 else (False if fm <= -35 and nfm <= -41 else None)
    b = True if mod >= -25 else (False if mod <= -40 and nmod <= -46 else None)
    if a is None or b is None:
        return 'undecided'
    return NAMES[(a, b)]


def take(path):
    m, rate, clip, floor, onsets, nfound = onsets_of(path)
    segs = [m[int((t + WIN[0]) * rate):int((t + WIN[1]) * rate)] for t in onsets]
    ctl1 = [i for i, (name, con) in enumerate(SEQ) if (name, con) == ('CTL', 1)]
    c2a, c2b = find_peak(segs[ctl1[0]], rate, 2 * F_NOM), find_peak(segs[ctl1[-1]], rate, 2 * F_NOM)
    f = c2a / 2
    q = int((onsets[0] - 0.65) * rate)
    quiet = m[q:q + len(segs[0])]
    noise = np.array([np.mean([fbmodel.amp(quiet, rate, k * f + d) ** 2 for d in range(-30, 31, 10)])
                      for k in range(1, KMAX + 1)])
    steps = np.diff(onsets)
    print(f'{path}: {rate} Hz, clipped {clip}, floor {floor:.1f} dBFS, onsets found {nfound}/{len(SEQ) - 1}, '
          f'spacing {steps.min():.3f}-{steps.max():.3f} s, f {f:.3f} Hz (nominal {F_NOM:.3f}), '
          f'2f first/last CTL1 {c2a:.3f}/{c2b:.3f} Hz')
    got = {}
    ctl_ok = True
    for (name, con), s in zip(SEQ, segs):
        P = np.array([fbmodel.amp(s, rate, k * f) ** 2 for k in range(1, KMAX + 1)])
        T = P.sum()
        fm, mod = l10((P[0] + P[4]) / T), l10(P[2] / T)
        nfm, nmod = l10((noise[0] + noise[4]) / T), l10(noise[2] / T)
        v = verdict(fm, mod, nfm, nmod)
        got.setdefault((name, con), []).append(v)
        if name == 'CTL' and v != EXPECT_CTL[con]:
            ctl_ok = False
        lines = ' '.join(f'{l10(p / T):6.1f}' for p in P)
        print(f'  {name} CON{con}  T {l10(T):6.1f}  L(k=1..8) {lines}  FM {fm:6.1f} (noise {nfm:6.1f})  '
              f'MOD {mod:6.1f} (noise {nmod:6.1f})  -> {v}')
    valid = nfound == len(SEQ) - 1 and clip == 0 and abs(c2a - c2b) <= 0.1 and ctl_ok
    print('  take valid:', valid)
    res = {}
    for key in (('BD', 0), ('BD', 1)):
        vs = got[key]
        res[key] = vs[0] if all(x == vs[0] for x in vs) else 'undecided'
        print(f'  BD CON{key[1]}: {vs} -> {res[key]}')
    return valid, res


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    anaws.WS_SEQ = list(range(len(SEQ)))
    anaws.INSTR = ['x']
    takes = []
    for path in sys.argv[1:]:
        valid, res = take(path)
        if valid:
            takes.append(res)
    print(f'valid takes: {len(takes)} of {len(sys.argv) - 1}')
    for key in (('BD', 0), ('BD', 1)):
        vs = [r[key] for r in takes]
        v = vs[0] if vs and all(x == vs[0] for x in vs) else 'undecided'
        print(f'BD CON{key[1]}: {vs} -> {v}')


if __name__ == '__main__':
    main()
