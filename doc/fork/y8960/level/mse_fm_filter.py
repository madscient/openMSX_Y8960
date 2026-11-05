"""MSX SOUND ENHANCER rev.2 の FM（OPLL）の経路の周波数特性を、回路図から計算する。
回路図の値は、回路図の著作権者の了承を得て、ここに写した。
ピン（MO・RO）から、差動増幅 IC8A の出力まで。理想オペアンプ、ピンは電圧源（出力インピーダンス 0）と仮定する。
値は回路図の読み取り: R7=R8=4.7k、R9=R10=4.7k、C12..C15=1500p、R11=R12=22k、R13=R14=33k。
   mse_fm_filter.py table
   mse_fm_filter.py apply IN.wav MARKS.txt OUT.wav [bd_mark_name]
"""
import sys
import wave

import numpy as np

R7 = R8 = R9 = R10 = 4.7e3
C12 = C13 = C14 = C15 = 1500e-12
R11 = R12 = 22e3
R13 = R14 = 33e3


def response(f, path):
    """path='RO' なら RO に 1V、MO を 0V。path='MO' ならその逆。出力 Vo / 1V を返す。"""
    f = np.atleast_1d(np.asarray(f, dtype=float))
    s = 2j * np.pi * f
    vr = 1.0 if path == 'RO' else 0.0
    vm = 1.0 if path == 'MO' else 0.0
    n = len(f)
    # 未知数: A_R, B_R, A_M, B_M, Vn, Vo
    M = np.zeros((n, 6, 6), dtype=complex)
    b = np.zeros((n, 6), dtype=complex)
    # A_R: (vr - A_R)/R7 = A_R s C12 + (A_R - B_R)/R9
    M[:, 0, 0] = 1 / R7 + s * C12 + 1 / R9
    M[:, 0, 1] = -1 / R9
    b[:, 0] = vr / R7
    # B_R: (A_R - B_R)/R9 = B_R s C14 + (B_R - Vn)/R11
    M[:, 1, 0] = -1 / R9
    M[:, 1, 1] = 1 / R9 + s * C14 + 1 / R11
    M[:, 1, 4] = -1 / R11
    # A_M
    M[:, 2, 2] = 1 / R8 + s * C13 + 1 / R10
    M[:, 2, 3] = -1 / R10
    b[:, 2] = vm / R8
    # B_M: (A_M - B_M)/R10 = B_M s C15 + (B_M - Vn)/R12
    M[:, 3, 2] = -1 / R10
    M[:, 3, 3] = 1 / R10 + s * C15 + 1 / R12
    M[:, 3, 4] = -1 / R12
    # + 入力: (B_M - Vn)/R12 = Vn/R13
    M[:, 4, 3] = 1 / R12
    M[:, 4, 4] = -(1 / R12 + 1 / R13)
    # - 入力: (B_R - Vn)/R11 + (Vo - Vn)/R14 = 0
    M[:, 5, 1] = 1 / R11
    M[:, 5, 4] = -(1 / R11 + 1 / R14)
    M[:, 5, 5] = 1 / R14
    x = np.linalg.solve(M, b[..., None])[..., 0]
    return x[:, 5]


def table():
    freqs = [20, 100, 500, 1000, 2000, 3000, 5000, 8000, 10000, 15000, 20000]
    ro = response(freqs, 'RO')
    mo = response(freqs, 'MO')
    r1 = response([1000], 'RO')[0]
    m1 = response([1000], 'MO')[0]
    print('Hz      RO path (dB, abs)  MO path (dB, abs)   RO rel 1kHz  MO rel 1kHz   MO/RO (dB)   RO phase  MO phase')
    for f, r, m in zip(freqs, ro, mo):
        print('%6d   %8.2f           %8.2f           %7.2f      %7.2f      %7.2f     %7.1f  %7.1f' % (
            f, 20 * np.log10(abs(r)), 20 * np.log10(abs(m)),
            20 * np.log10(abs(r) / abs(r1)), 20 * np.log10(abs(m) / abs(m1)),
            20 * np.log10(abs(m) / abs(r)), np.degrees(np.angle(r)), np.degrees(np.angle(m))))


def read_marks(path):
    marks = []
    with open(path, encoding='utf-8-sig') as fh:
        for line in fh:
            p = line.split()
            if len(p) == 2:
                try:
                    marks.append((float(p[0]), p[1]))
                except ValueError:
                    pass
    return marks


def apply(src, marks_path, dst, bd_name):
    with wave.open(src, 'rb') as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    assert width == 2
    x = np.frombuffer(raw, dtype='<i2').reshape(-1, ch).astype(np.float64) / 32768.0
    marks = read_marks(marks_path)
    t_bd = [t for t, nm in marks if nm == bd_name][0]
    split = int(t_bd * rate)
    out = np.zeros_like(x)
    for (lo, hi, path) in ((0, split, 'MO'), (split, n, 'RO')):
        seg = x[lo:hi]
        m = hi - lo
        nfft = 1 << int(np.ceil(np.log2(m * 2)))
        freqs = np.fft.rfftfreq(nfft, 1 / rate)
        h = response(freqs, path)
        # 1kHz の利得で割って 1 に正規化する。見るのは、楽音（1kHz）に対する各区間の相対値だけ
        h0 = response([1000.0], path)[0]
        h = h / abs(h0)
        for c in range(ch):
            spec = np.fft.rfft(seg[:, c], nfft)
            out[lo:hi, c] = np.fft.irfft(spec * h, nfft)[:m]
    pcm = np.clip(out, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype('<i2')
    with wave.open(dst, 'wb') as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    print('wrote', dst, 'rate', rate, 'channels', ch, 'split at %.2f s' % t_bd)


if __name__ == '__main__':
    if sys.argv[1] == 'table':
        table()
    elif sys.argv[1] == 'apply':
        apply(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv) > 5 else 'opll-bd')
