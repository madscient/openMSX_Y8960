"""OPL2 の EG の減衰とリリースの速さ（dB/s）を仮説ごとに出す。

仮説:
  real  : Nuked-OPL3 の OPL3_EnvelopeCalc と同じ規則。速さ = 4R + ksn >> (KSR ? 0 : 2)（リリースも同じ）。速さの上位が 12 未満は、
          EG の時計（2 サンプルに 1 回）で 2^-(12-hi) × (4+lo)/4 の割合で 1 単位（0.1875dB）進む
  y8960 : JTOPL（Y8960 の写し）。速さ = 4R + keycode >> (KSR ? 1 : 3)、リリースはさらに +2（jtopl_eg_ctrl.v の {rrate,1'b1}）。
          eg_cnt は毎サンプル進み（jtopl_eg.v、jtopl_eg_cnt.v）、上位 12 未満は (4+lo)/8 / 2^(11-hi) の割合で 2（10 ビットの単位
          0.09375dB）進む（jtopl_eg_step.v、jtopl_eg_pure.v）。上位 12 以上は毎サンプル dr_sum = 2/4/8/15
  pr16  : jotego/jtopl の現行。y8960 と同じで、上位 12 未満の歩だけが 1
keycode・ksn はどちらも block × 2 + fnum の b9（NTS = 0）。
"""
FS = 3579545 / 72
UNIT9 = 0.1875
UNIT10 = 0.09375
INCSTEP = [[0, 0, 0, 0], [1, 0, 0, 0], [1, 0, 1, 0], [1, 1, 1, 0]]
HYPS = ('real', 'y8960', 'pr16')


def ksn(block, fnum):
    return block * 2 + ((fnum >> 9) & 1)


def rate_of(hyp, r, ksr, block, fnum, release):
    if r == 0:
        return 0
    k = ksn(block, fnum)
    if hyp == 'real':
        return min(4 * r + (k >> (0 if ksr else 2)), 63)
    rate = 4 * r + (2 if release else 0) + (k >> (1 if ksr else 3))
    return 63 if rate >= 60 else rate


def speed(hyp, rate):
    if rate == 0:
        return 0.0
    hi, lo = min(rate >> 2, 15), rate & 3
    if hyp == 'real':
        if hi < 12:
            return 2.0 ** -(12 - hi) * (4 + lo) / 4 * FS / 2 * UNIT9
        tot = 0
        for t in range(4):
            for st in (0, 1):
                sh = (hi & 3) + INCSTEP[lo][t]
                if sh & 4:
                    sh = 4
                if not sh:
                    sh = st
                tot += (1 << (sh - 1)) if sh else 0
        return tot / 8 * FS * UNIT9
    if hi < 12:
        step = 1 if hyp == 'pr16' else 2
        return (4 + lo) / 8 / 2 ** (11 - hi) * FS * step * UNIT10
    return {12: 2, 13: 4, 14: 8, 15: 15}[hi] * FS * UNIT10


def predict(test):
    """test: dict(kind, r, ksr, block, fnum)。{仮説: (速さの番号, dB/s)}"""
    out = {}
    for h in HYPS:
        rt = rate_of(h, test['r'], test['ksr'], test['block'], test['fnum'], test['kind'] == 'R')
        out[h] = (rt, speed(h, rt))
    return out
