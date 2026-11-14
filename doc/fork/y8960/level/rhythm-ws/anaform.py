"""mkform.py のパッチを鳴らした録音を測り、リズム音の SD・CY・HH が、どの作り方（rhymodel.py の nuked / ymf262 / y8950）に
近いかを判定する。

    py anaform.py take1.wav [take2.wav ...]

打の位置合わせと、打ごとの区間 [立ち上がり + 10ms, + 410ms]・1/3 オクターブの帯域の値は anaws.py と同じ。

線の比べ方: 模型ごとに、同じ長さの区間をチップのレートで作り、200Hz-16kHz で近くの中央値より 15dB 以上突き出た線を強い順に
10 本取る。録音でその周波数の ±max(6Hz, 400ppm) に、近くの中央値より 10dB 以上、かつ最初の打の前の雑音の同じ所より 10dB 以上
突き出た線があれば「在る」。U[A|B] は、模型 A の線のうち模型 B に無い（B の同じ所の突き出しが 5dB 未満）ものが、録音に在る割合。

判定の基準（録音を見る前に決めた）:
  打ごと、A と B の組で: U[A|B] >= 0.7 かつ U[B|A] <= 0.3 なら A、逆なら B、ほかは「?」。
  YM3812 の形: (nuked, y8950) か (ymf262, y8950) の組で、YM3812 の側が勝ち、もう一方の組で y8950 が勝たない打。
  今の Y8950 の形: 両方の組で y8950 が勝つ打。
  音ごと（SD・CY・HH）、すべての回のすべての打が同じ側なら、その形。ほかは「決まらない」。
  鳴っていない打（RMS が打の前の床より 10dB 以上大きくない）があれば、その音は判定しない。
MULT が効くか（模型を使わない見方）: CY と HH の a と b の帯域の値の差 D（anaws.dist）を、同じ打の 1 巡目と 2 巡目の差と比べる。
  どの回でも D(a, b) >= 3dB かつ >= 3 × 繰り返しの差なら「効く」、どの回でも D(a, b) <= max(1dB, 1.5 × 繰り返しの差) なら
  「効かない」。今の Y8950 の形は効かず、YM3812 の形は効く。
"""
import sys

import numpy as np

import anaws
import rhymodel as M

LO, HI = 200.0, 16000.0
K = 10
PROM_MODEL = 15.0
PROM_FOUND = 10.0
ABSENT = 5.0
NEIGH = 150.0


def tol(f):
    return max(6.0, 400e-6 * f)


def spectrum(x, rate):
    x = x - x.mean()
    p = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    return np.fft.rfftfreq(len(x), 1 / rate), 10 * np.log10(p + 1e-20)


def peak_floor(fr, db, f0, t):
    d = np.abs(fr - f0)
    peak = float(db[d <= t].max())
    floor = float(np.median(db[(d > t + 10) & (d <= NEIGH)]))
    return peak, floor


def model_lines(fr, db):
    bw = fr[1] - fr[0]
    idx = np.where((fr > LO) & (fr < HI))[0]
    cand = []
    for i in idx:
        if db[i] >= db[i - 1] and db[i] > db[i + 1]:
            pk, fl = peak_floor(fr, db, fr[i], 2 * bw)
            if pk - fl >= PROM_MODEL:
                cand.append((db[i], fr[i]))
    chosen = []
    for _, f in sorted(cand, reverse=True):
        if all(abs(f - g) > 20 for g in chosen):
            chosen.append(f)
        if len(chosen) == K:
            break
    return chosen


def model_spectra(hit):
    n = int((anaws.WIN[1] + 0.05) * M.CHIP_RATE)
    a, b = int(anaws.WIN[0] * M.CHIP_RATE), int(anaws.WIN[1] * M.CHIP_RATE)
    out = {}
    for form in M.FORMS:
        x = M.render(form, hit[0], M.regs_of(hit), n)[a:b]
        out[form] = spectrum(x, M.CHIP_RATE)
    return out


def u_score(lines_a, spec_b, found):
    fr, db = spec_b
    use = []
    for f in lines_a:
        pk, fl = peak_floor(fr, db, f, tol(f))
        if pk - fl < ABSENT:
            use.append(found[f])
    return (float(np.mean(use)) if use else float('nan')), len(use)


def pair(ua, ub):
    if ua >= 0.7 and ub <= 0.3:
        return 'A'
    if ub >= 0.7 and ua <= 0.3:
        return 'B'
    return '?'


def analyse(path):
    m, rate, clip = anaws.read(path)
    db = anaws.frames_db(m, rate)
    n = len(M.HITS)
    floor0 = np.median(db[: int(1.0 / anaws.FRAME)])
    onsets, _ = anaws.align(db, floor0 + 20, n)
    a, b = int((onsets[0] - 0.6) / anaws.FRAME), int((onsets[0] - 0.1) / anaws.FRAME)
    floor = max(floor0, float(np.median(db[a:b])))
    onsets, nfound = anaws.align(db, floor + 20, n)
    seglen = int((anaws.WIN[1] - anaws.WIN[0]) * rate)
    n0 = int((onsets[0] - 0.5) * rate)
    noise = m[n0:n0 + seglen]
    nspec = spectrum(noise, rate)
    nb = anaws.band_levels(noise - noise.mean(), rate)
    steps = np.diff(onsets)
    print(f'{path}: {rate} Hz, clipped {clip}, floor {floor:.1f} dBFS, first hit {onsets[0]:.3f} s, '
          f'spacing {steps.min():.3f}-{steps.max():.3f} s, {n - 1 - nfound} of {n - 1} onsets predicted')
    hits = []
    for t, hit in zip(onsets, M.HITS):
        seg = m[int((t + anaws.WIN[0]) * rate):int((t + anaws.WIN[1]) * rate)]
        seg = seg - seg.mean()
        rms = 10 * np.log10(max(np.mean(seg ** 2), 1e-14))
        fr, sdb = spectrum(seg, rate)
        ms = model_spectra(hit)
        lines = {f: model_lines(*ms[f]) for f in M.FORMS}
        found = {}
        for form in M.FORMS:
            for f in lines[form]:
                pk, fl = peak_floor(fr, sdb, f, tol(f))
                npk, _ = peak_floor(nspec[0], nspec[1], f, tol(f))
                found[f] = (pk - fl >= PROM_FOUND) and (pk - npk >= PROM_FOUND)
        u = {}
        for x in M.FORMS:
            for y in M.FORMS:
                if x != y:
                    u[x, y] = u_score(lines[x], ms[y], found)
        vn = pair(u['nuked', 'y8950'][0], u['y8950', 'nuked'][0])
        vy = pair(u['ymf262', 'y8950'][0], u['y8950', 'ymf262'][0])
        if 'A' in (vn, vy) and 'B' not in (vn, vy):
            side = 'YM3812'
        elif vn == 'B' and vy == 'B':
            side = 'Y8950'
        else:
            side = '?'
        vny = pair(u['nuked', 'ymf262'][0], u['ymf262', 'nuked'][0])
        sub = {'A': 'nuked', 'B': 'ymf262', '?': '?'}[vny]
        audible = rms >= floor + 10
        print(f'  {hit[1]:5s} RMS {rms:6.1f}{"" if audible else " (silent)"}  '
              f'U[nuked|y8950] {u["nuked", "y8950"][0]:.2f} U[ymf262|y8950] {u["ymf262", "y8950"][0]:.2f} '
              f'U[y8950|nuked] {u["y8950", "nuked"][0]:.2f} U[y8950|ymf262] {u["y8950", "ymf262"][0]:.2f} -> {side:6s} '
              f'| U[nuked|ymf262] {u["nuked", "ymf262"][0]:.2f} ({u["nuked", "ymf262"][1]}) '
              f'U[ymf262|nuked] {u["ymf262", "nuked"][0]:.2f} ({u["ymf262", "nuked"][1]}) -> {sub}')
        hits.append({'name': hit[1], 'snd': hit[0], 'side': side, 'sub': sub, 'audible': audible,
                     'bands': anaws.band_levels(seg, rate)})
    return hits, nb


def mult_check(hits, nb, snd):
    by = {}
    for h in hits:
        by.setdefault(h['name'], []).append(h['bands'])
    a, b = by[f'{snd}-a'], by[f'{snd}-b']
    dab = [anaws.dist(a[k], b[k], nb) for k in range(len(a))]
    rep = [anaws.dist(a[0], a[1], nb), anaws.dist(b[0], b[1], nb)]
    return min(dab), max(dab), max(rep)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    allhits = []
    mult = {'CY': [], 'HH': []}
    for path in sys.argv[1:]:
        hits, nb = analyse(path)
        allhits += hits
        for snd in mult:
            mn, mx, rep = mult_check(hits, nb, snd)
            mult[snd].append((mn, mx, rep))
            print(f'  {snd}: D(a, b) {mn:.1f}-{mx:.1f} dB, repeat {rep:.1f} dB')
    print('decision:')
    for snd in ('SD', 'CY', 'HH'):
        hs = [h for h in allhits if h['snd'] == snd]
        sides = [h['side'] for h in hs]
        subs = [h['sub'] for h in hs]
        if not all(h['audible'] for h in hs):
            v = 'silent in some hit: no decision'
        elif all(s == 'YM3812' for s in sides):
            v = 'YM3812 form'
        elif all(s == 'Y8950' for s in sides):
            v = 'current Y8950 form'
        else:
            v = 'undecided'
        print(f'  {snd}: {v}  (hits: {" ".join(sides)}; nuked/ymf262: {" ".join(subs)})')
    for snd, vals in mult.items():
        if all(mn >= 3 and mn >= 3 * rep for mn, _, rep in vals):
            v = 'MULT matters'
        elif all(mx <= max(1.0, 1.5 * rep) for _, mx, rep in vals):
            v = 'MULT does not matter'
        else:
            v = 'undecided'
        print(f'  {snd} a/b: {v}  ' + ', '.join(f'({mn:.1f}, {rep:.1f})' for mn, _, rep in vals))


if __name__ == '__main__':
    main()
