"""mkhh.py のパッチ（HH だけ。波形 0 1 2 3 を 4 巡、続けて波形 0 を 4 打）を鳴らした録音を測る。

    py anahh.py take1.wav [take2.wav ...]

立ち上がりと打ごとの帯域の値は anaws.py と同じ。基準は同じ回の波形 0 の 8 打の帯域の値の平均。D(打) はその基準との
帯域の差。波形 0 の打は、自分を除いた 7 打の平均と比べる。

判定の基準（HH だけの録音を見る前に決めた）:
  ある回で、波形 w のどの打の D も波形 0 の打の D の最大より大きく、波形 w の D の平均が 3dB 以上なら、波形 w は分かれる。
  どの回でも波形 1-3 のどれかが分かれれば「掛かる」。
  どの回でも波形 1-3 のそれぞれの D の平均が、波形 0 の D の平均の 1.5 倍以下なら「掛からない」。ほかは「決まらない」。
"""
import sys

import numpy as np

import anaws

SEQ = [0, 1, 2, 3] * 4 + [0] * 4


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    anaws.WS_SEQ = SEQ
    anaws.INSTR = ['HH']
    takes_apply, takes_none = [], []
    for path in sys.argv[1:]:
        rate, clip, floor, onsets, hits, nb = anaws.analyse(path)
        steps = np.diff(onsets)
        print(f'{path}: clipped {clip}, floor {floor:.1f} dBFS, first hit {onsets[0]:.3f} s, '
              f'spacing {steps.min():.3f}-{steps.max():.3f} s')
        ws0 = [i for i, w in enumerate(SEQ) if w == 0]
        bl = [h[2] for h in hits]
        rms = [h[1] for h in hits]
        ref = np.mean([bl[i] for i in ws0], axis=0)
        d = {}
        for i, w in enumerate(SEQ):
            if w == 0:
                r = np.mean([bl[j] for j in ws0 if j != i], axis=0)
            else:
                r = ref
            d.setdefault(w, []).append((anaws.dist(bl[i], r, nb), rms[i]))
        d0max = max(x for x, _ in d[0])
        d0mean = float(np.mean([x for x, _ in d[0]]))
        sep_any = False
        none_all = True
        for w in (0, 1, 2, 3):
            ds = [x for x, _ in d[w]]
            ls = [y for _, y in d[w]]
            line = f'  WS{w}: D ' + ' '.join(f'{x:4.1f}' for x in ds) + \
                   f' | RMS ' + ' '.join(f'{y:6.1f}' for y in ls)
            if w:
                sep = min(ds) > d0max and np.mean(ds) >= 3
                sep_any |= sep
                none_all &= np.mean(ds) <= 1.5 * d0mean
                line += f'  separates: {sep}'
            print(line)
        takes_apply.append(sep_any)
        takes_none.append(none_all)
    if all(takes_apply):
        v = 'applies'
    elif all(takes_none):
        v = 'does not apply'
    else:
        v = 'undecided'
    print('HH:', v, '(per take separates:', takes_apply, ')')


if __name__ == '__main__':
    main()
