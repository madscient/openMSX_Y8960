"""mkform.py の録音で、打の前の床（リードの区間）の強い線と、帯域ごとのパワーの割合を見る。

    py floorpeek.py take.wav [...]
"""
import sys

import numpy as np

import anaform as A
import anaws
import rhymodel as M


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    for path in sys.argv[1:]:
        m, rate, clip = anaws.read(path)
        db = anaws.frames_db(m, rate)
        floor0 = np.median(db[: int(1.0 / anaws.FRAME)])
        onsets, _ = anaws.align(db, floor0 + 20, len(M.HITS))
        seg = m[int((onsets[0] - 2.5) * rate):int((onsets[0] - 0.1) * rate)]
        seg = seg - seg.mean()
        fr, sdb = A.spectrum(seg, rate)
        p = 10 ** (sdb / 10)
        tot = 10 * np.log10(np.mean(seg ** 2))
        bands = []
        for lo, hi in ((0, 200), (200, 2000), (2000, 8000), (8000, 24000)):
            sel = (fr >= lo) & (fr < hi)
            bands.append(10 * np.log10(p[sel].sum() / p.sum()))
        idx = [i for i in range(2, len(sdb) - 2) if sdb[i] >= sdb[i - 1] and sdb[i] > sdb[i + 1] and fr[i] > 20]
        idx = sorted(idx, key=lambda i: -sdb[i])[:8]
        print(f'{path}: lead before hit 0 RMS {tot:.1f} dBFS (head of file {floor0:.1f}); share of power '
              f'<200 {bands[0]:.1f}, 200-2k {bands[1]:.1f}, 2k-8k {bands[2]:.1f}, >8k {bands[3]:.1f} dB')
        print('  peaks: ' + ' '.join(f'{fr[i]:.1f}Hz({sdb[i] - sdb[idx[0]]:+.0f})' for i in idx))


if __name__ == '__main__':
    main()
