"""実物どうし（Y8950 と YM3812）と、実物と模型を、線の突き出しの並びで比べる。anaform.py の判定の後に足した見方で、
基準は録音を見た後に決めた（判定には使わない）。

    py cmpreal.py --a y1.wav y2.wav y3.wav --b m1.wav m2.wav m3.wav

打の種類ごとに、模型 3 つの強い線（各 10 本）の和集合の周波数で、録音の突き出し（近くの中央値との差）を取り、0〜40dB に
切り詰めたベクトルにする。2 本のベクトルの近さは、相関係数と、差の絶対値の平均。
"""
import argparse
import itertools
import sys

import numpy as np

import anaform as A
import anaws
import rhymodel as M

CAP = 40.0


def hits_of(path):
    m, rate, clip = anaws.read(path)
    db = anaws.frames_db(m, rate)
    floor0 = np.median(db[: int(1.0 / anaws.FRAME)])
    onsets, _ = anaws.align(db, floor0 + 20, len(M.HITS))
    a, b = int((onsets[0] - 0.6) / anaws.FRAME), int((onsets[0] - 0.1) / anaws.FRAME)
    floor = max(floor0, float(np.median(db[a:b])))
    onsets, _ = anaws.align(db, floor + 20, len(M.HITS))
    out = []
    for t, hit in zip(onsets, M.HITS):
        seg = m[int((t + anaws.WIN[0]) * rate):int((t + anaws.WIN[1]) * rate)]
        out.append((hit, A.spectrum(seg, rate)))
    return out


def vec(spec, freqs):
    fr, db = spec
    return np.clip([(lambda p: p[0] - p[1])(A.peak_floor(fr, db, f, A.tol(f))) for f in freqs], 0, CAP)


def near(x, y):
    return float(np.corrcoef(x, y)[0, 1]), float(np.mean(np.abs(x - y)))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', nargs='+', required=True)
    ap.add_argument('--b', nargs='+', required=True)
    args = ap.parse_args()
    ha = [h for p in args.a for h in hits_of(p)]
    hb = [h for p in args.b for h in hits_of(p)]
    for snd, name, _ in M.SET:
        hit = next(h for h in M.HITS if h[1] == name)
        ms = A.model_spectra(hit)
        freqs = sorted({f for form in M.FORMS for f in A.model_lines(*ms[form])})
        va = [vec(s, freqs) for h, s in ha if h[1] == name]
        vb = [vec(s, freqs) for h, s in hb if h[1] == name]
        vm = {form: vec(ms[form], freqs) for form in M.FORMS}
        rows = [('A-B', [near(x, y) for x in va for y in vb]),
                ('A-A', [near(x, y) for x, y in itertools.combinations(va, 2)]),
                ('B-B', [near(x, y) for x, y in itertools.combinations(vb, 2)])]
        rows += [(f'A-{form}', [near(x, vm[form]) for x in va]) for form in M.FORMS]
        rows += [(f'B-{form}', [near(x, vm[form]) for x in vb]) for form in M.FORMS]
        txt = '  '.join(f'{k} r {np.mean([c for c, _ in v]):.2f} |d| {np.mean([d for _, d in v]):4.1f}' for k, v in rows)
        print(f'{name:5s} ({len(freqs)} lines)  {txt}')


if __name__ == '__main__':
    main()
