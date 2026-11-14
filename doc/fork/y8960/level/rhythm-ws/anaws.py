"""mkws.py のパッチを鳴らした録音を測り、リズム音のスロットの波形選択がリズム音ごとに効くかを判定する。

    py anaws.py take1.wav [take2.wav ...]

区間: 25 打。名目 1000ms おき（800ms 鳴らして 200ms 休む）。並びは波形 0 1 2 3 0 × BD SD TT CY HH。

打ごとに、L+R の和の [立ち上がり + 10ms, 立ち上がり + 410ms] で RMS（dBFS）と、31.5Hz-16kHz の 1/3 オクターブの
帯域の値を取る。D は、同じ音の最初の波形 0 の打との帯域の値の差の二乗平均平方根。どちらかの打で雑音の帯域より
10dB 以上大きい帯域だけを使う。

判定の基準（録音を見る前に決めた）:
  - BD と TT（普通のスロットなので必ず変わる）が、どちらも 波形 1-3 の D の最大 >= 3dB かつ >= 3 × D(波形 0 の繰り返し)
    のときだけ、その録音の組を有効とする
  - SD・CY・HH: 波形 1-3 の D の最大 >= 3dB かつ >= 3 × D(波形 0 の繰り返し) なら「掛かる」、
    波形 1-3 の D の最大 <= max(1dB, 1.5 × D(波形 0 の繰り返し)) なら「掛からない」、ほかは「決まらない」
  - 最初の波形 0 の打が打の前の床より 10dB 以上大きくない音は、鳴っていないので判定しない
"""
import sys
import wave

import numpy as np

WS_SEQ = [0, 1, 2, 3, 0]
INSTR = ['BD', 'SD', 'TT', 'CY', 'HH']
STEP = 1.0
FRAME = 0.005
WIN = (0.010, 0.410)
# 試験のパッチの BD はキャリアの MULT が 0 で、約 38Hz の正弦波になる。帯域は 56Hz より下まで要る
BANDS = [31.5 * 2 ** (k / 3) for k in range(0, 28)]


def read(path):
    with wave.open(path, 'rb') as w:
        rate, ch, sw, n = w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes()
        assert sw == 2, 'expects 16-bit'
        x = np.frombuffer(w.readframes(n), dtype='<i2').astype(np.float64) / 32768
    x = x.reshape(-1, ch)
    clip = int(np.sum(np.abs(x) >= 32767 / 32768))
    m = x.sum(axis=1) / ch
    # 直流は録音の頭の無音だけから取る。半波の打は自分の直流を持つので、全体の平均を引くとそれが無音の側へ移る
    return m - m[:rate].mean(), rate, clip


def frames_db(m, rate):
    f = int(FRAME * rate)
    k = len(m) // f
    p = np.mean(m[:k * f].reshape(k, f) ** 2, axis=1)
    return 10 * np.log10(np.maximum(p, 1e-14))


def band_levels(seg, rate):
    w = np.hanning(len(seg))
    sp = np.abs(np.fft.rfft(seg * w)) ** 2
    fr = np.fft.rfftfreq(len(seg), 1 / rate)
    out = []
    for c in BANDS:
        lo, hi = c / 2 ** (1 / 6), c * 2 ** (1 / 6)
        sel = (fr >= lo) & (fr < hi)
        out.append(10 * np.log10(max(sp[sel].sum(), 1e-20)))
    return np.array(out)


def find_attacks(db, thr):
    # 立ち上がり: thr を超え、10ms で 10dB 以上上がる枠。同じ立ち上がりの後続の枠（300ms 以内）は捨てる
    attacks = []
    for k in range(2, len(db)):
        if db[k] > thr and db[k] - db[k - 2] > 10:
            if not attacks or k * FRAME - attacks[-1] > 0.3:
                attacks.append(k * FRAME)
    return attacks


def chain(attacks, start, n):
    # レジスタの書き込みで 1 歩は 1000ms より少し延び、実機ではときどき 1.4 秒ほどかかる。次の打は、前の打の
    # 0.9-1.45 秒後の最初の立ち上がりとする。立ち上がりが見えないほど静かな打は、典型の 1 歩先に置く
    onsets, found = [start], []
    for _ in range(1, n):
        prev = onsets[-1]
        cand = [t for t in attacks if prev + 0.9 <= t <= prev + 1.45]
        if cand:
            found.append(cand[0] - prev)
            onsets.append(cand[0])
        else:
            onsets.append(prev + (float(np.median(found)) if found else STEP))
    return onsets, found


def align(db, thr, n):
    # MGA は録音の途中でカートリッジの電源を入れ、電源投入と初期化が最初の打より前に立ち上がりを作る。その一部は
    # たまたま打の間隔に乗る。最初の打は、典型の長さ（0.97-1.08 秒）の歩をいちばん多く持つ並びの頭とし、同点は
    # 遅い方を取る。どのパッチも頭の 2 打は鳴るので、頭の 0.9-1.45 秒後に立ち上がりがあることを条件にする。無いと、
    # 静かな打が続くパッチで、電源投入の音から予測で進めた並びが本当の頭より多く数える
    attacks = find_attacks(db, thr)
    assert attacks, 'no hit found'
    best, key = None, None
    for s in attacks[:15]:
        if not any(s + 0.9 <= t <= s + 1.45 for t in attacks):
            continue
        onsets, found = chain(attacks, s, n)
        k = (sum(0.97 <= g <= 1.08 for g in found), len(found), s)
        if key is None or k > key:
            best, key = (onsets, len(found)), k
    return best


def analyse(path):
    m, rate, clip = read(path)
    db = frames_db(m, rate)
    n = len(WS_SEQ) * len(INSTR)
    floor0 = np.median(db[: int(1.0 / FRAME)])
    onsets, _ = align(db, floor0 + 20, n)
    # 打が乗る床は、最初の打の直前（リード。電源が入った後）のもの。MGA では録音の頭より約 20dB 高い
    a, b = int((onsets[0] - 0.6) / FRAME), int((onsets[0] - 0.1) / FRAME)
    floor = max(floor0, float(np.median(db[a:b])))
    onsets, nfound = align(db, floor + 20, n)
    print(f'  (floor head {floor0:.1f}, before first hit {floor:.1f} dBFS; '
          f'onsets: {n - 1 - nfound} of {n - 1} predicted, not found)')
    n0 = int((onsets[0] - 0.5) * rate)
    noise = m[n0:n0 + int((WIN[1] - WIN[0]) * rate)]
    nb = band_levels(noise, rate)
    hits = []
    for t in onsets:
        seg = m[int((t + WIN[0]) * rate):int((t + WIN[1]) * rate)]
        seg = seg - seg.mean()
        rms = 10 * np.log10(max(np.mean(seg ** 2), 1e-14))
        hits.append((t, rms, band_levels(seg, rate)))
    return rate, clip, floor, onsets, hits, nb


def dist(a, b, nb):
    use = (a > nb + 10) | (b > nb + 10)
    if not use.any():
        return float('nan')
    return float(np.sqrt(np.mean((a[use] - b[use]) ** 2)))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    summary = {}
    for path in sys.argv[1:]:
        rate, clip, floor, onsets, hits, nb = analyse(path)
        steps = np.diff(onsets)
        print(f'{path}: {rate} Hz, clipped {clip}, floor {floor:.1f} dBFS (5 ms frames), '
              f'first hit {onsets[0]:.3f} s, hit spacing {steps.min():.3f}-{steps.max():.3f} s')
        for i, name in enumerate(INSTR):
            ref = hits[i]
            row = []
            for k, ws in enumerate(WS_SEQ):
                t, rms, bl = hits[k * len(INSTR) + i]
                d = dist(bl, ref[2], nb)
                row.append((ws, rms, rms - ref[1], d))
            txt = '  '.join(f'WS{ws}:{rms:6.1f}dB d{dr:+5.1f} D{d:4.1f}' for ws, rms, dr, d in row)
            print(f'  {name}  {txt}')
            # 鳴っていない音を比べても、床どうしを比べるだけになる
            audible = ref[1] >= floor + 10
            summary.setdefault(name, []).append((max(r[3] for r in row[1:4]), row[4][3], audible))
    print('decision (max D over WS1-3, D of WS0 repeat):')
    verdict = {}
    for name in INSTR:
        vals = summary[name]
        dmax = min(v[0] for v in vals)   # いちばん弱い回
        drep = max(v[1] for v in vals)   # 繰り返しの差がいちばん大きい回
        if not all(v[2] for v in vals):
            v = 'silent at WS0 in some take: no decision'
        elif dmax >= 3 and dmax >= 3 * drep:
            v = 'applies'
        elif max(v[0] for v in vals) <= max(1.0, 1.5 * drep):
            v = 'does not apply'
        else:
            v = 'undecided'
        verdict[name] = v
        print(f'  {name}: ' + ', '.join(f'({a:.1f}, {b:.1f})' for a, b, _ in vals) + f' -> {v}')
    valid = verdict['BD'] == 'applies' and verdict['TT'] == 'applies'
    print('run valid (BD and TT affected):', valid)


if __name__ == '__main__':
    main()
