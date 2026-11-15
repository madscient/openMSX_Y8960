"""mkleak.py のパッチの録音を測る。

    py analeak.py take1.wav [...]

t0 = 録音の頭 1 秒の床より 30dB 以上の 5ms 枠が 0.5 秒続く最初の時刻（リズムの有効化。電源投入の瞬間の音は 0.3 秒ほどで消える）。
段 k（0 = 全部鳴る、1 = HH の後、2 = SD の後、3 = TT の後、4 = CY の後、5 = 4 スロットとも黙らせた後）の窓は
t0 + k × 2 × 1.02 秒 + [0.5, 1.5] 秒。窓の RMS（直流を引く）を dBFS で。

判定の基準（録音を見る前に決めた。合成の録音で、1 段ごとの dB の下がりでは 4 つが同じ大きさのとき決まらなかったので取り分にした）。
段 k-1 から k で消えた電力の、段 0 の電力に対する取り分 S_k:
  S_k >= 10% なら、そのスロットは「鳴っていた」。|S_k| <= 2% なら「鳴っていない」。ほかは「決まらない」
回が有効なのは、段 0 が床より 30dB 以上大きく、段 5 が床から 6dB 以内のとき。有効な回がすべて同じなら、それを結果とする。
"""
import sys

import numpy as np

import anaws

NAMES = ['HH', 'SD', 'TT', 'CY', 'all']
SEG = 1.02


def take(path):
    m, rate, clip = anaws.read(path)
    db = anaws.frames_db(m, rate)
    floor = float(np.median(db[:int(1.0 / anaws.FRAME)]))
    need = int(0.5 / anaws.FRAME)
    above = db > floor + 30
    t0 = None
    for k in range(len(db) - need):
        if above[k:k + need].all():
            t0 = k * anaws.FRAME
            break
    assert t0 is not None, 'no sustained noise'
    # MGA が電源を入れると床が上がる。比べる床は雑音が始まる直前のもの
    powered = float(np.median(db[int((t0 - 1.5) / anaws.FRAME):int((t0 - 0.3) / anaws.FRAME)]))
    lv = []
    clip = 0
    for k in range(6):
        a = t0 + k * 2 * SEG + 0.5
        s = m[int(a * rate):int((a + 1.0) * rate)]
        clip += int(np.sum(np.abs(s) >= 32767 / 32768))
        lv.append(10 * np.log10(max(np.mean((s - s.mean()) ** 2), 1e-14)))
    floor = powered
    valid = lv[0] >= floor + 30 and lv[5] <= floor + 6 and clip == 0
    res = {}
    parts = []
    for k in range(1, 6):
        d = lv[k - 1] - lv[k]
        share = (10 ** (lv[k - 1] / 10) - 10 ** (lv[k] / 10)) / 10 ** (lv[0] / 10)
        v = 'sounded' if share >= 0.10 else ('silent' if abs(share) <= 0.02 else 'undecided')
        res[NAMES[k - 1]] = v
        parts.append(f'{NAMES[k - 1]}: {lv[k]:6.1f} (D {d:5.1f}, share {100 * share:5.1f}%) -> {v}')
    print(f'{path}: clipped {clip}, floor {floor:.1f} dBFS, t0 {t0:.2f} s, step 0 {lv[0]:.1f} dBFS, valid {valid}')
    for p in parts:
        print('  ' + p)
    return valid, res


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    takes = []
    for p in sys.argv[1:]:
        valid, res = take(p)
        if valid:
            takes.append(res)
    print(f'valid takes: {len(takes)} of {len(sys.argv) - 1}')
    for n in NAMES[:4]:
        vs = [r[n] for r in takes]
        v = vs[0] if vs and all(x == vs[0] for x in vs) else 'undecided'
        print(f'{n}: {vs} -> {v}')


if __name__ == '__main__':
    main()
