"""mkeg.py のパッチを鳴らした録音を測り、減衰とリリースの速さが egmodel.py のどの仮説に合うかを判定する。

    py anaeg.py take1.wav [...]

立ち上がりと位置合わせは anaws.py と同じ（13 打はすべて鳴る）。打ごとに [立ち上がり - 20ms, + 980ms] の解析信号の大きさ（包絡）を
dB にし、0.5ms の移動平均を掛ける。床は最初の打の前の無音の包絡の中央値。
  減衰: 立ち上がりの前後 [-15ms, +10ms] の最大を頂点とし、頂点の 0.3ms 後から、頂点 - 45dB・床 + 12dB・立ち上がり + 790ms
        （鍵を離す）のいちばん早いところまで
  リリース: [+100ms, +250ms] の中央値を L0 とし、+200ms より後で L0 - 2dB を切ったところから、L0 - 45dB・床 + 12dB・+980ms の
        いちばん早いところまで
この区間で dB を時間に直線で当て、傾きを速さ（dB/s）とする。区間の落ち幅が 5dB 未満か、点が 50 未満の打は測れないとする。

判定の基準（録音を見る前に決めた）。打ごとに、測った速さ m と仮説の予測 p の比で:
  |ln(m/p)| <= ln 1.12 なら「合う」、|ln(m/p)| >= ln 1.25 なら「外れる」
回が有効なのは、13 打の立ち上がりがすべて見つかり、クリップが無く、判定する 12 打が測れたとき。仮説ごとに、有効な回のすべての打で
「合う」なら「合う」、有効な回のどれでも 1 打以上「外れる」なら「外れる」、ほかは「決まらない」
A-D12（速さ 48 以上）は表示だけで判定に使わない。JTOPL の予測 9322dB/s では 40dB の落ちが 4.3ms（484.6Hz の 2 周期）で終わり、
解析信号の包絡では測れない（合成の録音で、予測の 0.30〜0.52 倍にばらついた）
"""
import sys

import numpy as np

import anaws
import egmodel
from mkeg import TESTS

FIT, MISS = np.log(1.12), np.log(1.25)
SHOW_ONLY = {'A-D12'}


def onsets_of(path):
    m, rate, clip = anaws.read(path)
    db = anaws.frames_db(m, rate)
    n = len(TESTS)
    floor0 = np.median(db[: int(1.0 / anaws.FRAME)])
    onsets, _ = anaws.align(db, floor0 + 20, n)
    a, b = int((onsets[0] - 0.6) / anaws.FRAME), int((onsets[0] - 0.1) / anaws.FRAME)
    floor = max(floor0, float(np.median(db[a:b])))
    onsets, nfound = anaws.align(db, floor + 20, n)
    return m, rate, clip, onsets, nfound


def envelope_db(x, rate):
    n = len(x)
    sp = np.fft.fft(x - x.mean())
    h = np.zeros(n)
    h[0] = 1
    h[1:(n + 1) // 2] = 2
    if n % 2 == 0:
        h[n // 2] = 1
    p = np.abs(np.fft.ifft(sp * h)) ** 2
    k = max(1, int(0.0005 * rate))
    p = np.convolve(p, np.ones(k) / k, mode='same')
    return 10 * np.log10(np.maximum(p, 1e-14))


def first_below(e, start, level):
    idx = np.nonzero(e[start:] < level)[0]
    return start + int(idx[0]) if len(idx) else len(e)


def measure(m, rate, t0, test, floor):
    pre = 0.020
    seg = m[int((t0 - pre) * rate):int((t0 + 0.980) * rate)]
    e = envelope_db(seg, rate)
    at = lambda s: int((s + pre) * rate)
    if test['kind'] == 'D':
        lo, hi = at(-0.015), at(0.010)
        pk = lo + int(np.argmax(e[lo:hi]))
        start = pk + int(0.0003 * rate)
        top = e[pk]
        end = min(first_below(e, start, top - 45), first_below(e, start, floor + 12), at(0.790))
    else:
        top = float(np.median(e[at(0.100):at(0.250)]))
        start = first_below(e, at(0.200), top - 2)
        end = min(first_below(e, start, top - 45), first_below(e, start, floor + 12), at(0.980))
    if end - start < 50:
        return float('nan'), 0.0
    t = np.arange(start, end) / rate
    slope = np.polyfit(t, e[start:end], 1)[0]
    fall = float(e[start] - e[end - 1])
    if fall < 5:
        return float('nan'), fall
    return -slope, fall


def take(path):
    m, rate, clip, onsets, nfound = onsets_of(path)
    q = int((onsets[0] - 0.65) * rate)
    floor = float(np.median(envelope_db(m[q:q + int(0.6 * rate)], rate)))
    print(f'{path}: {rate} Hz, clipped {clip}, envelope floor {floor:.1f} dBFS, onsets found {nfound}/{len(TESTS) - 1}, '
          f'spacing {np.diff(onsets).min():.3f}-{np.diff(onsets).max():.3f} s')
    rows = {}
    ok = True
    for t, t0 in zip(TESTS, onsets):
        sp, fall = measure(m, rate, t0, t, floor)
        p = egmodel.predict(t)
        shown = ' (shown only)' if t['name'] in SHOW_ONLY else ''
        if np.isnan(sp):
            ok = ok and bool(shown)
            print(f'  {t["name"]:8s} not measurable (fall {fall:.1f} dB){shown}')
            continue
        r = {h: float(np.log(sp / p[h][1])) for h in egmodel.HYPS}
        if not shown:
            rows[t['name']] = r
        print(f'  {t["name"]:8s} {sp:8.1f} dB/s over {fall:4.1f} dB   '
              + '  '.join(f'{h}: {p[h][1]:7.1f} ({np.exp(r[h]):.2f})' for h in egmodel.HYPS) + shown)
    valid = ok and clip == 0 and nfound == len(TESTS) - 1
    print('  take valid:', valid)
    return valid, rows


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    anaws.WS_SEQ = list(range(len(TESTS)))
    anaws.INSTR = ['x']
    takes = []
    for path in sys.argv[1:]:
        valid, rows = take(path)
        if valid:
            takes.append(rows)
    print(f'valid takes: {len(takes)} of {len(sys.argv) - 1}')
    for h in egmodel.HYPS:
        fit_all = bool(takes) and all(abs(r[k][h]) <= FIT for r in takes for k in r)
        miss_each = bool(takes) and all(any(abs(r[k][h]) >= MISS for k in r) for r in takes)
        nfit = [int(sum(abs(r[k][h]) <= FIT for k in r)) for r in takes]
        nmiss = [int(sum(abs(r[k][h]) >= MISS for k in r)) for r in takes]
        v = 'fits' if fit_all else ('misses' if miss_each else 'undecided')
        print(f'  {h:6s} fit {nfit} miss {nmiss} of {len(TESTS) - len(SHOW_ONLY)} per take -> {v}')


if __name__ == '__main__':
    main()
