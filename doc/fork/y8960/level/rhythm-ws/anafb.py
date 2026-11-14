"""mkfb.py のパッチを鳴らした録音を測る。

    py anafb.py take1.wav [...]

立ち上がりと位置合わせは anaws.py と同じ（20 打はすべて鳴る）。打ごとに [立ち上がり + 10ms, + 410ms] の 1/3 オクターブ
（100Hz-16kHz）の帯域の値を取る。減衰する音でも時間の重みが平らになるよう、2048 点のハン窓を 75% ずつ重ねて電力を平均する。
D は 2 つの帯域の値の差の二乗平均平方根。どちらかが雑音の帯域より 10dB 以上大きい帯域だけを使う。

判定の基準（録音を見る前に決めた）。音ごと（対照・TT・HH）、回ごとに:
  Dx = FB0 の打の平均と FB7 の打の平均の D。Dw = 各打と、同じ FB の残りの打の平均との D の最大
  Dx >= 3dB かつ Dx >= 3 × Dw なら「掛かる」、Dx <= max(1dB, 1.5 × Dw) なら「掛からない」、ほかは「決まらない」
  回が有効なのは、対照が「掛かる」ときだけ。音ごとに、有効な回がすべて同じなら、それを結果とする
"""
import sys

import numpy as np

import anaws

SEQ = [('CTL', 0), ('CTL', 7)] * 2 + [('TT', 0), ('TT', 7)] * 4 + [('HH', 0), ('HH', 7)] * 4
WIN = (0.010, 0.410)
BANDS = [100 * 2 ** (k / 3) for k in range(0, 23)]
NFFT = 2048


def band_power(seg, rate):
    seg = seg - seg.mean()
    w = np.hanning(NFFT)
    hop = NFFT // 4
    frames = [seg[i:i + NFFT] for i in range(0, len(seg) - NFFT + 1, hop)]
    sp = np.mean([np.abs(np.fft.rfft(f * w)) ** 2 for f in frames], axis=0)
    fr = np.fft.rfftfreq(NFFT, 1 / rate)
    out = []
    for c in BANDS:
        lo, hi = c / 2 ** (1 / 6), c * 2 ** (1 / 6)
        out.append(max(sp[(fr >= lo) & (fr < hi)].sum(), 1e-20))
    return np.array(out)


def db(p):
    return 10 * np.log10(p)


def dist(a, b, nb):
    use = (a > nb + 10) | (b > nb + 10)
    if not use.any():
        return float('nan')
    return float(np.sqrt(np.mean((a[use] - b[use]) ** 2)))


def judge(hits, nb):
    g0 = [h for f, h in hits if f == 0]
    g7 = [h for f, h in hits if f == 7]
    m0, m7 = db(np.mean(g0, axis=0)), db(np.mean(g7, axis=0))
    dx = dist(m0, m7, nb)
    dw = 0.0
    for g in (g0, g7):
        for i, h in enumerate(g):
            rest = db(np.mean([x for j, x in enumerate(g) if j != i], axis=0))
            dw = max(dw, dist(db(h), rest, nb))
    if dx >= 3 and dx >= 3 * dw:
        v = 'applies'
    elif dx <= max(1.0, 1.5 * dw):
        v = 'does not apply'
    else:
        v = 'undecided'
    return dx, dw, v


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    anaws.WS_SEQ = list(range(len(SEQ)))
    anaws.INSTR = ['x']
    result = {}
    for path in sys.argv[1:]:
        m, rate, clip = anaws.read(path)
        _, _, floor, onsets, _, _ = anaws.analyse(path)
        n0 = int((onsets[0] - 0.5) * rate)
        nb = db(band_power(m[n0:n0 + int((WIN[1] - WIN[0]) * rate)], rate))
        print(f'{path}: clipped {clip}, floor {floor:.1f} dBFS, first hit {onsets[0]:.3f} s, '
              f'spacing {np.diff(onsets).min():.3f}-{np.diff(onsets).max():.3f} s')
        per = {}
        for (name, fb), t in zip(SEQ, onsets):
            seg = m[int((t + WIN[0]) * rate):int((t + WIN[1]) * rate)]
            rms = 10 * np.log10(max(np.mean((seg - seg.mean()) ** 2), 1e-14))
            per.setdefault(name, []).append((fb, band_power(seg, rate), rms))
        verdicts = {}
        for name in ('CTL', 'TT', 'HH'):
            hits = [(f, p) for f, p, _ in per[name]]
            dx, dw, v = judge(hits, nb)
            rms = ' '.join(f'FB{f}:{r:6.1f}' for f, _, r in per[name])
            print(f'  {name:3s} Dx {dx:5.1f}  Dw {dw:4.1f}  -> {v:15s} RMS {rms}')
            verdicts[name] = v
        valid = verdicts['CTL'] == 'applies'
        print('  take valid (control affected):', valid)
        if valid:
            for name in ('TT', 'HH'):
                result.setdefault(name, []).append(verdicts[name])
    for name in ('TT', 'HH'):
        vs = result.get(name, [])
        v = vs[0] if vs and all(x == vs[0] for x in vs) else 'undecided'
        print(f'{name}: {vs} -> {v}')


if __name__ == '__main__':
    main()
