"""ADPCM と FM・SSG の大きさを比べる音列を書き出す。書式は tones.txt と同じ。

    py adpcm-tones.py OUT/adpcm.txt
    py adpcm-tones.py --target MSXAUDIO [--r08 02] OUT/adpcm-y8950.txt     Y8950 の実チップ用

書き出した音列は tones-mga.ps1 -Sequence（Y8950 は -Target MSXAUDIO も）/ Y8960_TONES で流し、
tone-levels.py --seq OUT/adpcm.txt --ref opl2-center で測る。音列は 2 万行を超えるので
リポジトリには置かず、測るたびにここで作る（同じ入力からは同じものができる）。

ADPCM は最大振幅（±32767）の正弦波と矩形波を、1 周期 16 サンプル・約 8.3kHz（DELTA-N 2AABh）で
3 秒ずつ。ループ再生は使わない（折り返しで復号器の状態が初期値に戻るため）。
符号化は 1 サンプルずつ 16 通りを復号してみて、目標に最も近いものを選ぶ。復号の式は Y8950 の
ADPCM（ハードウェアは jt10_adpcmb、openMSX は Y8960Adpcm::calcSample）で、上位ニブルが先。
比べる相手は tones.txt と同じ SSG2・OPL2・OPM の 1ch（約 1kHz）。
"""

import argparse
import math
import sys

F2 = [57, 57, 57, 57, 77, 102, 128, 153]
PERIOD = 16
SECONDS = 3.0
DELTA_N = 0x2AAB
RATE = DELTA_N * 49716 / 65536


def encode(target):
    x, step, out = 0, 127, []
    for t in target:
        best = None
        for c in range(16):
            mag = ((2 * (c & 7) + 1) * step) >> 3
            nx = min(max(x - mag if c & 8 else x + mag, -32768), 32767)
            if best is None or abs(t - nx) < best[0]:
                best = (abs(t - nx), c, nx)
        _, c, x = best
        step = min(max((F2[c & 7] * step) >> 6, 127), 24576)
        out.append((c, x))
    return out


def fundamental(xs):
    # 先頭 0.5 秒を除いた区間で、1 周期 16 サンプルの成分の振幅
    a = xs[int(RATE * 0.5) // PERIOD * PERIOD:]
    re = sum(v * math.cos(2 * math.pi * i / PERIOD) for i, v in enumerate(a))
    im = sum(v * math.sin(2 * math.pi * i / PERIOD) for i, v in enumerate(a))
    return 2 * math.hypot(re, im) / len(a)


def pack(codes):
    return bytes((codes[i] << 4) | codes[i + 1] for i in range(0, len(codes), 2))


REFERENCE = '''
# SSG2 ch A: 998.8Hz、トーンだけ（tones.txt と同じ）
mem 7FF0 10
mem 7FF1 70
mem 7FF0 11
mem 7FF1 00
mem 7FF0 17
mem 7FF1 3E

# OPL2 ch1: キャリア 1 つの正弦波、999.9Hz（tones.txt と同じ）
io C0 BD
io C1 00
io C0 20
io C1 21
io C0 23
io C1 21
io C0 40
io C1 3F
io C0 43
io C1 00
io C0 60
io C1 00
io C0 63
io C1 F0
io C0 80
io C1 0F
io C0 83
io C1 0F
io C0 E0
io C1 00
io C0 E3
io C1 00
io C0 C0
io C1 00
io C0 A0
io C1 93

# OPM ch1: C2 だけの正弦波、約 988Hz（tones.txt と同じ）
io 7E 20
io 7F C7
io 7E 60
io 7F 7F
io 7E 68
io 7F 7F
io 7E 70
io 7F 7F
io 7E 80
io 7F 00
io 7E 88
io 7F 00
io 7E 90
io 7F 00
io 7E 58
io 7F 01
io 7E 78
io 7F 00
io 7E 98
io 7F 1F
io 7E B8
io 7F 00
io 7E D8
io 7F 00
io 7E F8
io 7F 0F
io 7E 28
io 7F 5D
io 7E 30
io 7F 00
'''

PLAY_REFERENCE = '''
mark ssg-center
mem 7FF0 18
mem 7FF1 0F
wait 2500
mem 7FF0 18
mem 7FF1 00
wait 1000

mark opl2-center
io C0 B0
io C1 36
wait 2500
io C0 B0
io C1 16
wait 1000

mark opm-center
io 7E 08
io 7F 40
wait 2500
io 7E 08
io 7F 00
wait 1000
'''


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out')
    ap.add_argument('--target', choices=['Y8960', 'MSXAUDIO'], default='Y8960',
                    help='MSXAUDIO は Y8950 の実チップ用。比べる相手は OPL2 ch1 だけになる')
    ap.add_argument('--r08', type=lambda s: int(s, 16), default=0x00,
                    help='レジスタ 08h に書く値（16 進）。既定 00（256Kbit の RAM）')
    a = ap.parse_args()
    # REFERENCE と PLAY_REFERENCE は空行で区切った SSG2・OPL2・OPM の 3 つの塊
    keep = [0, 1, 2] if a.target == 'Y8960' else [1]
    reference = '\n\n'.join(REFERENCE.strip().split('\n\n')[i] for i in keep)
    play_reference = '\n\n'.join(PLAY_REFERENCE.strip().split('\n\n')[i] for i in keep)
    n = int(RATE * SECONDS) // PERIOD * PERIOD
    waves = {
        'sine': [round(32767 * math.sin(2 * math.pi * i / PERIOD)) for i in range(n)],
        'square': [32767 if i % PERIOD < PERIOD // 2 else -32767 for i in range(n)],
    }
    data, ranges, notes = b'', {}, []
    for name, target in waves.items():
        enc = encode(target)
        start = len(data) // 4
        data += pack([c for c, _ in enc])
        ranges[name] = (start, len(data) // 4 - 1)
        got = fundamental([x for _, x in enc])
        want = fundamental(target)
        notes.append(f'#   {name:6s}: 復号した波形の基本波 {got:.0f}（目標の波形は {want:.0f}、'
                     f'{20 * math.log10(got / want):+.2f}dB）')
    assert len(data) % 4 == 0

    w = []
    w.append('# adpcm-tones.py が書き出した音列。手で直さず、adpcm-tones.py を直して作り直す。')
    w.append(f'# ADPCM は 1 周期 {PERIOD} サンプル、{RATE:.1f}Hz（{RATE / PERIOD:.1f}Hz の音）で {n} サンプルずつ、'
             f'計 {len(data)} バイト。')
    w.extend(notes)
    w.append(f'# 対象 {a.target}、08h = {a.r08:02X}h')
    w.append('')
    if a.target == 'Y8960':
        w.append('mem 7FFF 05                 # I/O Enabler2: b0 OPL2、b2 OPM')
    w.append('')
    w.append(reference)
    w.append('')
    w.append('# ADPCM のメモリに書く（07h=60h）。BUF_RDY は読まない。MGA の 1 回の書き込みは')
    w.append('# メモリへの書き込みより十分に長い。BUF_RDY と EOS はリセット値のままマスクしておき、/INT を出さない')
    stop = len(data) // 4 - 1
    for r, v in ((0x07, 0x01), (0x08, a.r08), (0x09, 0x00), (0x0A, 0x00), (0x0B, stop & 0xFF),
                 (0x0C, stop >> 8), (0x10, DELTA_N & 0xFF), (0x11, DELTA_N >> 8), (0x12, 0xFF),
                 (0x07, 0x60), (0x04, 0x80)):
        w.append(f'io C0 {r:02X}')
        w.append(f'io C1 {v:02X}')
    w.append('io C0 0F')
    w.extend(f'io C1 {b:02X}' for b in data)
    for r, v in ((0x07, 0x01), (0x04, 0x80), (0x04, 0x18)):
        w.append(f'io C0 {r:02X}')
        w.append(f'io C1 {v:02X}')
    w.append('')
    w.append('wait 1000')
    w.append('')
    w.append(play_reference)
    w.append('')
    for name, (s, e) in ranges.items():
        w.append(f'io C0 09\nio C1 {s & 0xFF:02X}\nio C0 0A\nio C1 {s >> 8:02X}')
        w.append(f'io C0 0B\nio C1 {e & 0xFF:02X}\nio C0 0C\nio C1 {e >> 8:02X}')
        w.append(f'mark adpcm-{name}')
        w.append('io C0 07\nio C1 A0                    # START + MEMORY DATA、一回再生')
        w.append(f'wait {round(SECONDS * 1000)}')
        w.append('io C0 07\nio C1 01')
        w.append('wait 1000')
        w.append('')
    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(w) + '\n')
    print(f'{a.out}: {len(data)} バイト、{sum(1 for x in w for _ in x.splitlines())} 行')
    for s in notes:
        print(s[1:])


if __name__ == '__main__':
    main()
