"""ssg-polarity.txt を鳴らした録音から、SSG の極性と、ミキサーを書き換えた瞬間の段差を測り、録音どうしを比べる。

    py ssg-polarity.py REF.wav OTHER.wav...

録音は tones-mga.wav（実機）か tones-openmsx.wav（openMSX）。印の時刻は同じ名前の .txt から読む。
REF には openMSX の録音を渡し、OTHER に実機の録音と、比べたい別の openMSX の録音を渡す。

極性: 印から 0.5〜1.5 秒を左右の和にし、REF との正規化した相互相関を、ずれ ±1 周期の範囲で取る。鋸歯と半波の正弦波は
上下が非対称なので、向きが同じなら最大がおよそ +1、逆なら最小がおよそ -1 になり、反対側の極値は絶対値が小さい
（鋸歯でおよそ 0.5、半波の正弦波でおよそ 0.7）。絶対値の大きい方の極値の符号を、その音源の向きとする。
録音の経路の反転は 4 つの音源に同じだけ掛かるので、SSG の向きを他の 3 つと比べて判定する。

段差: 印の前後で、1 周期（998.8Hz）ぶんの平均の差が最大になる時刻を探し、その差を段差とする。1 周期の平均は矩形波を
消すので、矩形波の区間でも平均の動きだけが残る。段差は、同じ書き換えで矩形波の振れ幅が変わった量で割る（振れ幅は、
書き換えの後 0.3〜0.9 秒の、上半分と下半分の中央値の差）。0 と振れ幅の間を振れる出力なら、矩形波の段差は ±0.5、
直流の段差は ±1.0 になる。振れ幅は向きを持たないので、段差の符号は、出力の向きと録音の経路の向きの積になる。
録音の経路の高域通過は、窓の 1 周期の間にも段差を減らす。経路ごとに減り方が違うので、録音どうしは、同じ録音の dc-off
（SSG の音量 15 から 0。ミキサーを通らない段差）で割った値（2 つ目の表）で比べる。経路が線形なら、同じ窓で測った
直流の段差どうしの比は経路に左右されない。
矩形波の段差は判別が弱い: 中心の上下に振れる矩形波でも、窓が書き換えをまたぐと振れ幅の変化の 1/4 ほどの見かけの段差が出る。
"""

import argparse
import re
import sys
import wave
from pathlib import Path

import numpy as np

POLARITY = ['ssg-saw', 'scc-saw', 'opll-half', 'opl2-half']
SAW_HZ = 134.45
SQUARE_HZ = 1789772.5 / (16 * 112)

# 段差の区間: (印, 書き換えの前の振れ幅を測る区間, 後の区間)。直流の区間は矩形波が無いので、同じ設定の矩形波の区間で代える
STEPS = [
    ('sq-vol-half', 'sq-ref', 'sq-vol-half'),
    ('sq-vol-full', 'sq-vol-half', 'sq-vol-full'),
    ('sq-pan-left', 'sq-vol-full', 'sq-pan-left'),
    ('sq-pan-center', 'sq-pan-left', 'sq-pan-center'),
    ('dc-on', None, 'sq-ref'),
    ('dc-vol-half', 'sq-ref', 'sq-vol-half'),
    ('dc-vol-full', 'sq-vol-half', 'sq-vol-full'),
    ('dc-pan-left', 'sq-vol-full', 'sq-pan-left'),
    ('dc-pan-center', 'sq-pan-left', 'sq-pan-center'),
    ('dc-off', None, 'sq-ref'),
]


def read_wav(path):
    with wave.open(str(path), 'rb') as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width == 2:
        x = np.frombuffer(raw, '<i2').astype(np.float64) / 32768.0
    elif width == 4:
        x = np.frombuffer(raw, '<i4').astype(np.float64) / float(1 << 31)
    else:
        sys.exit(f'{path}: {width * 8}bit の WAV は読めない')
    x = x.reshape(-1, ch)
    if ch == 1:
        x = np.repeat(x, 2, axis=1)
    return x[:, :2], rate


def read_marks(path):
    # tones-mga.ps1 は Set-Content -Encoding UTF8 で BOM を付ける。ログの行（"  123.4 ms  ..."）は形が違うので拾わない
    out = {}
    for line in path.with_suffix('.txt').read_text(encoding='utf-8-sig').splitlines():
        m = re.match(r'^(\d+\.\d+) (\S+)\s*$', line)
        if m:
            out[m.group(2)] = float(m.group(1))
    return out


class Rec:
    def __init__(self, path):
        self.path = Path(path)
        self.x, self.rate = read_wav(self.path)
        self.marks = read_marks(self.path)
        need = POLARITY + [s[0] for s in STEPS] + ['sq-ref']
        missing = [k for k in need if k not in self.marks]
        if missing:
            sys.exit(f'{self.path}: 印が足りない: {" ".join(missing)}')

    def seg(self, t0, t1):
        return self.x[int(t0 * self.rate):int(t1 * self.rate)]


def resample(x, rate_from, rate_to):
    if rate_from == rate_to:
        return x
    n = int(len(x) * rate_to / rate_from)
    t = np.arange(n) / rate_to
    src = np.arange(len(x)) / rate_from
    return np.stack([np.interp(t, src, x[:, c]) for c in range(x.shape[1])], axis=1)


def xcorr(a, b):
    # a は長さ N、b は長さ N + 2L。b の各窓（ずれ 0..2L）から平均を引いて、a との正規化した相関を返す
    a = a - a.mean()
    n = len(a)
    num = np.correlate(b, a, 'valid')
    c1 = np.concatenate([[0.0], np.cumsum(b)])
    c2 = np.concatenate([[0.0], np.cumsum(b * b)])
    s1 = c1[n:] - c1[:-n]
    s2 = c2[n:] - c2[:-n]
    var = np.maximum(s2 - s1 * s1 / n, 1e-30)
    return num / np.sqrt(var * (a @ a))


def polarity(ref, other):
    out = {}
    lag = int(other.rate / SAW_HZ) + 2
    for name in POLARITY:
        t = ref.marks[name]
        a = ref.seg(t + 0.5, t + 1.5)
        a = resample(a, ref.rate, other.rate).sum(axis=1)
        u = other.marks[name]
        b = other.seg(u + 0.5, u + 1.5 + 2 * lag / other.rate).sum(axis=1)
        b = b[:len(a) + 2 * lag]
        r = xcorr(a, b)
        hi, lo = float(r.max()), float(r.min())
        out[name] = (hi, lo, 1 if hi >= -lo else -1)
    return out


def swing(rec, name):
    t = rec.marks[name]
    x = rec.seg(t + 0.3, t + 0.9)
    out = []
    for c in range(2):
        v = x[:, c]
        m = np.median(v)
        hi, lo = v[v > m], v[v <= m]
        out.append(float(np.median(hi) - np.median(lo)) if len(hi) and len(lo) else 0.0)
    return np.array(out)


def step(rec, name):
    # 窓は書き換えの直後の 1 周期に限る。実機の録音の経路は、段差を 3ms ほどで消し、10ms あたりで逆に振れる。
    # 間をあけた窓では、その逆振れを段差と読む
    w = int(round(rec.rate / SQUARE_HZ))
    t = rec.marks[name]
    i0 = max(int((t - 0.05) * rec.rate), w)
    i1 = int((t + 0.4) * rec.rate)
    x = rec.x[i0 - w:i1 + w]
    c = np.concatenate([np.zeros((1, 2)), np.cumsum(x, axis=0)])
    after = (c[2 * w:] - c[w:-w]) / w
    before = (c[w:-w] - c[:-2 * w]) / w
    d = after - before
    k = int(np.argmax(np.abs(d).sum(axis=1)))
    return d[k], (i0 + k) / rec.rate - t


def steps(rec):
    out = {}
    for name, pre, post in STEPS:
        d, dt = step(rec, name)
        if pre is None:
            base = swing(rec, post)
        else:
            base = swing(rec, post) - swing(rec, pre)
        ratio = np.where(np.abs(base) > 1e-4, d / np.where(base == 0, 1, base), np.nan)
        out[name] = (d, base, ratio, dt)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('ref')
    ap.add_argument('others', nargs='+')
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    ref = Rec(args.ref)
    recs = [Rec(p) for p in args.others]

    print(f'REF: {ref.path}（{ref.rate}Hz）')
    print('\n== 極性（REF との相関の最大 / 最小 → 向き）==')
    for rec in recs:
        p = polarity(ref, rec)
        print(f'\n{rec.path}（{rec.rate}Hz）')
        for name in POLARITY:
            hi, lo, s = p[name]
            print(f'  {name:10s} 最大 {hi:+.3f}  最小 {lo:+.3f}  → {"同じ" if s > 0 else "逆"}')
        others = [p[n][2] for n in POLARITY[1:]]
        ssg = p['ssg-saw'][2]
        if len(set(others)) != 1:
            print('  判定: SCC・OPLL・OPL2 の向きがそろわない。SSG の向きは決められない')
        elif ssg == others[0]:
            print('  判定: SSG と他の 3 つの向きの関係が REF と同じ')
        else:
            print('  判定: SSG だけが REF と逆（他の 3 つとの関係が REF と反対）')

    allrecs = [ref] + recs
    table = [steps(r) for r in allrecs]
    for title, norm in [('段差 / 振れ幅の変化。L, R。dc-on・dc-off は 段差 / 振れ幅', False),
                        ('上の値を、同じ録音の dc-off の絶対値で割ったもの', True)]:
        print(f'\n== 段差（{title}）==')
        print('  ' + ' ' * 14 + ''.join(f'{r.path.parent.name[:22]:>24s}' for r in allrecs))
        for name, _, _ in STEPS:
            cells = []
            for t in table:
                ratio = t[name][2]
                if norm:
                    ratio = ratio / np.abs(t['dc-off'][2])
                cells.append('  '.join('   nan' if np.isnan(v) else f'{v:+.3f}' for v in ratio))
            print(f'  {name:14s}' + ''.join(f'{c:>24s}' for c in cells))
    print('\n  （参考）振れ幅 sq-ref L, R と、段差を見つけた時刻の印からのずれ（秒）')
    for r, t in zip(allrecs, table):
        sw = swing(r, 'sq-ref')
        dts = ' '.join(f'{t[n][3]:+.3f}' for n, _, _ in STEPS)
        print(f'  {r.path.parent.name}: 振れ幅 {sw[0]:.4f}, {sw[1]:.4f}  ずれ {dts}')


if __name__ == '__main__':
    main()
