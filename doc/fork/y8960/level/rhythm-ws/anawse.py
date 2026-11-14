"""mkwse.py のパッチ（HH だけ。01h = 00h を 4 打、20h を 4 打、00h を 4 打、20h を 4 打）を鳴らした録音を測る。

    py anawse.py take1.wav [...]

判定の基準（このパッチの録音を見る前に決めた）:
  どの回でも、20h のどの打も 00h のどの打より 20dB 以上小さければ「20h が HH を消す」。
  どの回でも、2 つの組の RMS の平均の差が 3dB 以内なら「影響なし」。ほかは「決まらない」。
"""
import sys

import numpy as np

import anaws

SEQ = [0x00] * 4 + [0x20] * 4 + [0x00] * 4 + [0x20] * 4


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    anaws.WS_SEQ = SEQ
    anaws.INSTR = ['HH']
    sil, none = [], []
    for path in sys.argv[1:]:
        rate, clip, floor, onsets, hits, nb = anaws.analyse(path)
        a = [h[1] for h, r in zip(hits, SEQ) if r == 0x00]
        b = [h[1] for h, r in zip(hits, SEQ) if r == 0x20]
        print(f'{path}: clipped {clip}, floor {floor:.1f} dBFS, first hit {onsets[0]:.3f} s')
        print('  01h=00h RMS ' + ' '.join(f'{x:6.1f}' for x in a))
        print('  01h=20h RMS ' + ' '.join(f'{x:6.1f}' for x in b))
        sil.append(max(b) <= min(a) - 20)
        none.append(abs(np.mean(a) - np.mean(b)) <= 3)
    v = '20h silences HH' if all(sil) else 'no effect' if all(none) else 'undecided'
    print('verdict:', v)


if __name__ == '__main__':
    main()
