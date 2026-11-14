"""mkform.py の打で、模型ごとの線が録音にどれだけ突き出ているかを並べる。anaform.py が「?」を出した打の理由を見るためのもの。

    py cydetail.py take.wav [打の名前 ...]
"""
import sys

import numpy as np

import anaform as A
import anaws
import rhymodel as M


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    path = sys.argv[1]
    names = sys.argv[2:] or ['CY-a', 'CY-b']
    m, rate, clip = anaws.read(path)
    db = anaws.frames_db(m, rate)
    floor0 = np.median(db[: int(1.0 / anaws.FRAME)])
    onsets, _ = anaws.align(db, floor0 + 20, len(M.HITS))
    a, b = int((onsets[0] - 0.6) / anaws.FRAME), int((onsets[0] - 0.1) / anaws.FRAME)
    floor = max(floor0, float(np.median(db[a:b])))
    onsets, _ = anaws.align(db, floor + 20, len(M.HITS))
    seglen = int((anaws.WIN[1] - anaws.WIN[0]) * rate)
    n0 = int((onsets[0] - 0.5) * rate)
    nspec = A.spectrum(m[n0:n0 + seglen], rate)
    seen = set()
    for t, hit in zip(onsets, M.HITS):
        if hit[1] not in names or hit[1] in seen:
            continue
        seen.add(hit[1])
        seg = m[int((t + anaws.WIN[0]) * rate):int((t + anaws.WIN[1]) * rate)]
        fr, sdb = A.spectrum(seg, rate)
        ms = A.model_spectra(hit)
        print(f'== {hit[1]}')
        for form in M.FORMS:
            for f in A.model_lines(*ms[form]):
                pk, fl = A.peak_floor(fr, sdb, f, A.tol(f))
                npk, _ = A.peak_floor(*nspec, f, A.tol(f))
                prom = {g: (lambda p: p[0] - p[1])(A.peak_floor(*ms[g], f, A.tol(f))) for g in M.FORMS}
                print(f'  {form:7s} {f:8.1f} Hz  rec {pk - fl:5.1f} dB (noise {pk - npk:5.1f})  model prom ' +
                      ' '.join(f'{g} {prom[g]:5.1f}' for g in M.FORMS))


if __name__ == '__main__':
    main()
