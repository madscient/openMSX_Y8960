"""OPL2 の演算子 1 つ（変調器だけ、FB あり）を、表とビット幅をまねて作る。仮説ごとの倍音の形を出す。

仮説（和の幅、シフトの基数）:
  real  : 2 つ前までの出力の和を 14 ビットで取り、>> (9 - FB)（YM3812-LLE fmopl2.c:1294-1315、Nuked-OPL3 opl3.c:699）
  y8960 : 和を 13 ビットで取って溢れを捨て、>>> (9 - FB)（Y8960 の opl2_patch/jtopl_op.v:145,150）
  pr16  : 和を 13 ビットで取り、>>> (10 - FB)（jotego/jtopl の現行 hdl/jtopl_op.v:128,133）
  wide10: 和を 14 ビットで取り、>> (10 - FB)（比べるためだけ）
表は Nuked-OPL3 の logsinrom・exprom と 256 項とも同じ（JTOPL の jtopl_logsin・jtopl_exprom とも同じ）。
"""
import numpy as np

FS = 3579545 / 72
INC = 4640   # A0h=44h、ブロック 4、MULT 1 の位相の増分（19 ビット）。440.0Hz
LOGSIN = np.array([round(-np.log2(np.sin((i + 0.5) / 256 * np.pi / 2)) * 256) for i in range(256)])
EXPROM = np.array([round(2 ** ((255 - i) / 256) * 1024) for i in range(256)])

HYP = {'real': (14, 9), 'y8960': (13, 9), 'pr16': (13, 10), 'wide10': (14, 10)}


def calcsin(phase, env):
    phase &= 0x3FF
    neg = (phase & 0x200) != 0
    idx = (phase & 0xFF) ^ 0xFF if phase & 0x100 else phase & 0xFF
    level = int(LOGSIN[idx]) + (env << 3)
    if level > 0x1FFF:
        level = 0x1FFF
    out = (int(EXPROM[level & 0xFF]) << 1) >> (level >> 8)
    return ~out if neg else out


def wrap(x, bits):
    m = 1 << bits
    x &= m - 1
    return x - m if x & (m >> 1) else x


def run(fb, tl, hyp, mult=1, n=32768):
    """env は TL だけ（EG は減衰 0 で止まっている）"""
    bits, base = HYP[hyp]
    env = tl << 2
    inc = INC * mult
    ph = 0
    o1 = o2 = 0
    out = np.empty(n)
    for k in range(n):
        mod = (wrap(o1 + o2, bits) >> (base - fb)) if fb else 0
        o = calcsin((ph >> 9) + mod, env)
        out[k] = o
        o2, o1 = o1, o
        ph = (ph + inc) & 0x7FFFF
    return out


def bh(n):
    a = (0.35875, 0.48829, 0.14128, 0.01168)
    t = 2 * np.pi * np.arange(n) / (n - 1)
    return a[0] - a[1] * np.cos(t) + a[2] * np.cos(2 * t) - a[3] * np.cos(3 * t)


def amp(seg, rate, f):
    """Blackman-Harris 窓を掛けた、周波数 f ちょうどの DFT の大きさ（相対値）"""
    n = len(seg)
    x = (seg - seg.mean()) * bh(n)
    return float(abs(np.dot(x, np.exp(-2j * np.pi * f * np.arange(n) / rate))))


def predict(kmax=8):
    """{(hyp, fb, tl): [H2/H1 .. Hkmax/H1] dB}"""
    f0 = INC * FS / 2 ** 19
    out = {}
    for hyp in HYP:
        for tl in (0, 12):
            for fb in range(0, 8):
                x = run(fb, tl, hyp)
                h = np.array([amp(x, FS, k * f0) for k in range(1, kmax + 1)])
                out[(hyp, fb, tl)] = 20 * np.log10(np.maximum(h[1:] / h[0], 1e-12))
    return out
