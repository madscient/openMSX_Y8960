"""tones.txt を鳴らした録音から、区間ごとの基本波の振幅を測り、実機と openMSX を比べる。

    py tone-levels.py EMU.wav              openMSX の録音だけを測る
    py tone-levels.py EMU.wav HW.wav       実機と比べ、<volume> の案を出す
    py tone-levels.py --seq rhythm.txt --rel bd=ch7-melody EMU.wav [HW.wav]
                                           区間どうしの差を、録音ごとに出す（--ref B は全区間を B と比べる）

区間は録音の音量から切り出し、tones.txt の mark の順に対応づける。数が合わなければ止まる。
振幅は区間の中ほど（前後 0.5 秒を除く）を Hann 窓で FFT し、300-3000Hz の最大のピークの
主ローブ（前後 5 ビン）のエネルギーから、同じエネルギーの正弦波の振幅として出す。
基本波だけを見るので、矩形波の高調波がアナログ段で削られても、直流分があっても値は動かない。
"""

import argparse
import math
import sys
import wave
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEVICES = {
    'ssg': 'Y8960 SSGS',
    'scc': 'Y8960 SCC',
    'opll': 'Y8960 OPLL',
    'opl2': 'Y8960 OPL2',
    'opm': 'Y8960 OPM',
}
FRAME = 0.010
MIN_SEGMENT = 1.0
TRIM = 0.5
LOBE = 5


def read_wav(path):
    with wave.open(str(path), 'rb') as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if width == 2:
        x = np.frombuffer(raw, '<i2').astype(np.float64) / 32768.0
    elif width == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        x = np.where(v >= 1 << 23, v - (1 << 24), v).astype(np.float64) / float(1 << 23)
    elif width == 4:
        x = np.frombuffer(raw, '<i4').astype(np.float64) / float(1 << 31)
    else:
        sys.exit(f'{path}: {width * 8}bit の WAV は読めない')
    x = x.reshape(-1, ch)
    if ch == 1:
        x = np.repeat(x, 2, axis=1)
    return x[:, :2], rate


def labels(seq):
    out = []
    for line in Path(seq).read_text(encoding='utf-8').splitlines():
        f = line.split('#', 1)[0].split()
        if f and f[0] == 'mark':
            out.append(f[1])
    return out


def segments(x, rate):
    hop = int(rate * FRAME)
    n = len(x) // hop
    fr = x[:n * hop].reshape(n, hop, 2)
    fr = fr - fr.mean(axis=1, keepdims=True)
    level = np.sqrt((fr ** 2).mean(axis=1)).max(axis=1)
    floor = np.percentile(level, 10)
    peak = level.max()
    # 床から 20dB 上か、最大から 45dB 下の高い方。openMSX の無音は 0 なので床だけでは決まらない
    th = max(floor * 10.0, peak * 10 ** (-45 / 20))
    on = level > th
    segs, start = [], None
    for i, v in enumerate(np.append(on, False)):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if (i - start) * FRAME >= MIN_SEGMENT:
                segs.append((start * hop, i * hop))
            start = None
    return segs, th


def tone(x, rate, a, b):
    t = int(TRIM * rate)
    y = x[a + t:b - t]
    if len(y) < rate // 4:
        sys.exit('区間が短すぎる')
    n = len(y)
    w = np.hanning(n)
    freqs = np.fft.rfftfreq(n, 1.0 / rate)
    band = (freqs >= 300) & (freqs <= 3000)
    res = []
    for c in range(2):
        s = np.fft.rfft((y[:, c] - y[:, c].mean()) * w)
        p = np.abs(s) ** 2
        k = int(np.argmax(np.where(band, p, 0)))
        lo, hi = max(k - LOBE, 0), k + LOBE + 1
        amp = 2.0 * math.sqrt(p[lo:hi].sum() / (n * (w ** 2).sum()))
        res.append((freqs[k], amp))
    clipped = int((np.abs(y) >= 0.9999).sum())
    return res, clipped


def db(a):
    return 20 * math.log10(a) if a > 0 else float('-inf')


def measure(path, names):
    x, rate = read_wav(path)
    segs, th = segments(x, rate)
    print(f'{path}: {rate}Hz、{len(x) / rate:.1f} 秒、区間 {len(segs)} 個（閾値 {db(th):.1f} dBFS）')
    if len(segs) != len(names):
        for a, b in segs:
            print(f'  {a / rate:7.2f}-{b / rate:7.2f} 秒')
        sys.exit(f'区間の数が mark の数 {len(names)} と合わない')
    out = {}
    for name, (a, b) in zip(names, segs):
        ((fl, al), (fr, ar)), clipped = tone(x, rate, a, b)
        out[name] = (al, ar)
        mark = f'  飽和 {clipped} サンプル' if clipped else ''
        print(f'  {name:12s} {a / rate:6.2f}-{b / rate:6.2f} 秒  {fl:7.1f}Hz  '
              f'L {db(al):7.2f}  R {db(ar):7.2f} dBFS{mark}')
    return out


def relative(recs, pairs):
    # L と R の平均で比べる。定位は中央の区間どうしを比べる前提
    print('\n区間どうしの差（dB、L と R の平均）')
    head = ''.join(f'{n:>10s}' for n, _ in recs)
    print(f'  {"":26s}{head}' + ('  実機 - openMSX' if len(recs) == 2 else ''))
    for p, q in pairs:
        v = [(db(r[p][0]) + db(r[p][1]) - db(r[q][0]) - db(r[q][1])) / 2 for _, r in recs]
        tail = f'  {v[1] - v[0]:+10.2f}' if len(v) == 2 else ''
        print(f'  {p + " - " + q:26s}' + ''.join(f'{x:+10.2f}' for x in v) + tail)


def volumes(xml):
    root = ET.parse(xml).getroot()
    out = {}
    for e in root.iter():
        dev = e.get('id')
        if dev in DEVICES.values():
            v = e.find('sound/volume')
            if v is not None:
                out[dev] = int(v.text)
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('emu')
    ap.add_argument('hw', nargs='?')
    ap.add_argument('--seq', default=HERE / 'tones.txt')
    ap.add_argument('--xml', default=HERE.parents[3] / 'share' / 'extensions' / 'HRA_Y8960.xml')
    ap.add_argument('--rel', action='append', default=[], metavar='A=B',
                    help='区間 A の大きさを区間 B との差で出す。何度でも書ける')
    ap.add_argument('--ref', metavar='B', help='すべての区間を区間 B との差で出す')
    a = ap.parse_args()

    names = labels(a.seq)
    pairs = [tuple(r.split('=', 1)) for r in a.rel]
    if a.ref:
        pairs += [(n, a.ref) for n in names if n != a.ref]
    for p in pairs:
        if len(p) != 2 or not set(p) <= set(names):
            sys.exit(f'--rel / --ref の区間が音列に無い: {"=".join(p)}')
    recs = [('openMSX', measure(a.emu, names))]
    if a.hw:
        recs.append(('実機', measure(a.hw, names)))
    if pairs:
        relative(recs, pairs)
    if not a.hw:
        return
    emu, hw = recs[0][1], recs[1][1]

    print('\n実機 - openMSX（dB）')
    diff = {}
    for n in names:
        dl, dr = db(hw[n][0]) - db(emu[n][0]), db(hw[n][1]) - db(emu[n][1])
        diff[n] = (dl, dr)
        print(f'  {n:12s} L {dl:+7.2f}  R {dr:+7.2f}')

    print('\n定位: 左端と中央の差（dB）。実機と openMSX で同じなら定位の掛け方が同じ')
    for chip in DEVICES:
        c, l = f'{chip}-center', f'{chip}-left'
        if c in hw and l in hw:
            print(f'  {chip:5s} L: 実機 {db(hw[l][0]) - db(hw[c][0]):+6.2f}  openMSX {db(emu[l][0]) - db(emu[c][0]):+6.2f}'
                  f'   R: 実機 {db(hw[l][1]) - db(hw[c][1]):+7.2f}  openMSX {db(emu[l][1]) - db(emu[c][1]):+7.2f}')

    # 比は中央の区間の差で決まる。全体の大きさは自由なので、3 通りの揃え方を並べる
    if not all(f'{chip}-center' in diff for chip in DEVICES):
        return
    cur = volumes(a.xml)
    d = {chip: sum(diff[f'{chip}-center']) / 2 for chip in DEVICES if f'{chip}-center' in diff}
    raw = {chip: cur[DEVICES[chip]] * 10 ** (v / 20) for chip, v in d.items()}
    ref = sum(d.values()) / len(d)
    ways = [
        ('平均を保つ', 10 ** (-ref / 20)),
        ('最大を 30000', 30000 / max(raw.values())),
        ('SSGS を今の値に', cur[DEVICES['ssg']] / raw['ssg']),
    ]
    print(f'\n<volume> の案（{a.xml} の値から。補正の平均は {ref:+.2f}dB）')
    print('  ' + ' ' * 12 + '    今  ' + ''.join(f'{n:>16s}' for n, _ in ways) + '   平均を引いた差')
    for chip, v in d.items():
        dev = DEVICES[chip]
        cols = ''.join(f'{round(raw[chip] * f):>16d}' for _, f in ways)
        print(f'  {dev:12s} {cur[dev]:>6d}{cols}   {v - ref:+.2f}dB')


if __name__ == '__main__':
    main()
