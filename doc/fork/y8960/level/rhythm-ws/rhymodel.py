"""リズム音の SD・CY・HH の作り方の模型。包絡は 0dB で持続し、出力は全振幅を 1 とする（試験のパッチは TL 16 だが、
線の位置と突き出しは大きさによらない）。

    nuked  : Nuked-OPL3 の OPL3_PhaseGenerate（rm_xor に hh3^tc5、CY の位相は 080h / 280h）
    ymf262 : openMSX の YMF262（MAME 由来。genPhaseHighHat / genPhaseSnare / genPhaseCymbal。hh3 単独、CY は 100h / 300h）
    y8950  : openMSX の Y8950（calc_slot_snare / calc_slot_cym / calc_slot_hat。位相の表を引かない）

雑音の発生器は 1 サンプルに 1 歩進める。実物と雑音の並びは合わないので、比べるのは決まった成分（線スペクトル）だけ。
regs は {'f7': (fnum, block), 'f8': (fnum, block), 'm_hh': MULT, 'm_sd': MULT, 'm_tc': MULT}。
"""
import numpy as np

CHIP_RATE = 3579545 / 72
MT = [1, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 20, 24, 24, 30, 30]   # 2 × MULT（MULT 0 は 1/2）
FORMS = ['nuked', 'ymf262', 'y8950']


def phase_inc(fnum, block, mult):
    # Nuked: ((fnum << block) >> 1) * mt >> 1。openMSX の Y8950: ((fnum * mt) << block) >> 2。どちらも 19 ビットの位相
    return (((fnum << block) >> 1) * MT[mult]) >> 1


def phases(fnum, block, mult, n):
    acc = (np.arange(n, dtype=np.int64) * phase_inc(fnum, block, mult)) & 0x7FFFF
    return (acc >> 9).astype(np.int64)


def sin_out(ph):
    return np.sin(2 * np.pi * (ph + 0.5) / 1024)


def lfsr_nuked(n):
    out = np.empty(n, dtype=np.int64)
    s = 1
    for i in range(n):
        out[i] = s & 1
        b = ((s >> 14) ^ s) & 1
        s = (s >> 1) | (b << 22)
    return out


def lfsr_ymf262(n):
    out = np.empty(n, dtype=np.int64)
    s = 1
    for i in range(n):
        if s & 1:
            s ^= 0x800302
        s >>= 1
        out[i] = s & 1
    return out


def lfsr_y8950(n):
    out = np.empty(n, dtype=np.int64)
    s = 0xFFFF
    for i in range(n):
        if s & 1:
            s ^= 0x24000
        s >>= 1
        out[i] = s & 1
    return out


def y8950_noise_ab(f7, f8, n):
    da = f7[0] << f7[1]
    db = f8[0] << f8[1]
    a = np.empty(n, dtype=np.int64)
    b = np.empty(n, dtype=np.int64)
    pa = pb = 0
    for i in range(n):
        pa = (pa + da) & ((0x40 << 11) - 1)
        if (pa >> 11) == 0x3F:
            pa = 0
        a[i] = 1 if pa & (0x03 << 11) else 0
        pb = (pb + db) & ((0x10 << 11) - 1)
        b[i] = 1 if pb & (0x0A << 11) else 0
    return a, b


def render(form, sound, regs, n):
    f7, f8 = regs['f7'], regs['f8']
    hh = phases(*f7, regs['m_hh'], n)
    tc = phases(*f8, regs['m_tc'], n)
    sd = phases(*f7, regs['m_sd'], n)
    bit = lambda p, k: (p >> k) & 1
    if form == 'nuked':
        nz = lfsr_nuked(n)
        x = (bit(hh, 2) ^ bit(hh, 7)) | (bit(hh, 3) ^ bit(tc, 5)) | (bit(tc, 3) ^ bit(tc, 5))
        if sound == 'HH':
            ph = (x << 9) | np.where((x ^ nz) == 1, 0xD0, 0x34)
        elif sound == 'SD':
            h8 = bit(hh, 8)
            ph = (h8 << 9) | ((h8 ^ nz) << 8)
        else:
            ph = (x << 9) | 0x80
        return sin_out(ph)
    if form == 'ymf262':
        nz = lfsr_ymf262(n)
        r1 = (bit(hh, 2) ^ bit(hh, 7)) | bit(hh, 3)
        r2 = bit(tc, 3) ^ bit(tc, 5)
        if sound == 'HH':
            up = (r1 | r2) == 1
            ph = np.where(up, np.where(nz == 1, 0x2D0, 0x234), np.where(nz == 1, 0x34, 0xD0))
        elif sound == 'SD':
            ph = ((hh & 0x100) + 0x100) ^ (nz << 8)
        else:
            ph = np.where((r2 | r1) == 1, 0x300, 0x100)
        return sin_out(ph)
    if form == 'y8950':
        nz = lfsr_y8950(n)
        w = np.where(nz == 1, 0.5, -0.5)
        a, b = y8950_noise_ab(f7, f8, n)
        na = np.where(a == 1, 0.5, -0.5)
        nb = np.where(b == 1, 0.5, -0.5)
        if sound == 'SD':
            sq = np.where(bit(sd, 9) == 1, 1.0, -1.0)
            return (sq + w) / 2
        if sound == 'CY':
            return (na + nb) / 2
        return (w + na + nb) / 4
    raise ValueError(form)


F7 = (659, 5)     # 999.9Hz
F8 = (863, 5)     # 1309.4Hz
SET = [
    ('SD', 'SD-a', {'m_hh': 1, 'm_sd': 3, 'm_tc': 1}),
    ('SD', 'SD-b', {'m_hh': 2, 'm_sd': 1, 'm_tc': 1}),
    ('CY', 'CY-a', {'m_hh': 1, 'm_sd': 1, 'm_tc': 1}),
    ('CY', 'CY-b', {'m_hh': 1, 'm_sd': 1, 'm_tc': 4}),
    ('HH', 'HH-a', {'m_hh': 1, 'm_sd': 1, 'm_tc': 1}),
    ('HH', 'HH-b', {'m_hh': 4, 'm_sd': 1, 'm_tc': 1}),
]
HITS = SET * 2


def regs_of(hit):
    return dict(hit[2], f7=F7, f8=F8)
