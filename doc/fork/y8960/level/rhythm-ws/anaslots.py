"""mkslots.py のパッチの録音を測り、鍵を押していないのに音の出る位置にある EG のスロットを数える。

    py anaslots.py take1.wav [...]

窓は終わりの合図から逆算する（実チップは BDh=20h で雑音が出ないので、最初の合図は使えない）。
t_end = 床（録音の頭 1 秒）より 30dB 以上の 5ms 枠が 0.5 秒続く区間のうち、最後のものの頭（ch0 の鍵）。区間を 1.02 秒として、
ch c の窓は t_end − (4 + 2 × (8 − c)) × 1.02 + 0.5 秒から 1 秒、静かな窓は t_end − 2 × 1.02 + 0.5 秒から 1 秒（ch8 の F-Num を
0 に戻した後）、旋律に戻した後の窓は t_end − 21.5 × 1.02 秒から 1 秒、合図の窓は t_end + 0.1 秒から 0.6 秒。
各窓で 440Hz（変調器）と 880Hz（キャリア）の大きさを Blackman-Harris 窓の DFT で測り、正弦波の振幅の dBFS にする（L）。
床 N は、静かな窓 2 つ（旋律に戻した後、ch8 の F-Num を 0 に戻した後）で、f ± 50Hz を 5Hz おきに取った電力の平均。50Hz・60Hz の
倍音から 4Hz 以内の点は除く（1 点や 7 点では平均のばらつきが大きく、合成の録音で静かなスロットが「決まらない」になった）。

判定の基準（録音を見る前に決めた）。スロットごとに:
  L − N >= 30dB で「鳴る位置にある」、L − N <= 10dB で「静か」（雑音の 1 点の電力が平均の 10 倍を超える確率は約 5 × 10^-5）、
  ほかは「決まらない」
回が有効なのは、合図の 2 本の線（F-Num 200h の 388Hz と 777Hz）が床より 30dB 以上大きく、旋律に戻した後の窓と静かな窓の RMS の差が
6dB 以内で、測る窓にクリップが無いとき。有効な回がすべて同じなら、それを結果とする。
"""
import sys

import numpy as np

import anaws
import fbmodel

SEG = 1.02
F = 0x244 * 3579545 / 72 * 2 ** 3 / 2 ** 19
FM = 0x200 * 3579545 / 72 * 2 ** 3 / 2 ** 19


def rms_db(s):
    return 10 * np.log10(max(np.mean((s - s.mean()) ** 2), 1e-14))


def line_db(s, rate, f):
    return 20 * np.log10(max(2 * fbmodel.amp(s, rate, f) / fbmodel.bh(len(s)).sum(), 1e-9))


def take(path):
    m, rate, _ = anaws.read(path)
    db = anaws.frames_db(m, rate)
    floor0 = float(np.median(db[:int(1.0 / anaws.FRAME)]))
    need = int(0.5 / anaws.FRAME)
    above = db > floor0 + 30
    starts = [k for k in range(1, len(db) - need) if above[k:k + need].all() and not above[k - 1]]
    assert starts, 'no marker'
    t_end = starts[-1] * anaws.FRAME

    def win(a, n=1.0):
        return m[int(a * rate):int((a + n) * rate)]
    quiet = win(t_end - 2 * SEG + 0.5)
    back = win(t_end - 21.5 * SEG)
    mark = win(t_end + 0.1, 0.6)

    def floor_at(f):
        pts = [f + d for d in range(-50, 51, 5)
               if min(abs((f + d) - 50 * round((f + d) / 50)), abs((f + d) - 60 * round((f + d) / 60))) > 4]
        return 10 * np.log10(np.mean([10 ** (line_db(s, rate, p) / 10) for s in (quiet, back) for p in pts]))
    nq = {f: floor_at(f) for f in (F, 2 * F)}
    mk = {k: line_db(mark, rate, k) for k in (FM, 2 * FM)}
    nq_m = {k: floor_at(k) for k in (FM, 2 * FM)}
    res = {}
    clip = 0
    rows = []
    for c in range(9):
        s = win(t_end - (4 + 2 * (8 - c)) * SEG + 0.5)
        clip += int(np.sum(np.abs(s) >= 32767 / 32768))
        cells = []
        for name, f in (('mod', F), ('car', 2 * F)):
            L = line_db(s, rate, f)
            d = L - nq[f]
            v = 'audible' if d >= 30 else ('quiet' if d <= 10 else 'undecided')
            res[(c, name)] = v
            cells.append(f'{name} {L:6.1f} dBFS (+{d:5.1f}) {v:9s}')
        rows.append(f'  ch{c}  RMS {rms_db(s):6.1f}  ' + '  '.join(cells))
    valid = (min(mk[FM] - nq_m[FM], mk[2 * FM] - nq_m[2 * FM]) >= 30 and abs(rms_db(back) - rms_db(quiet)) <= 6
             and clip == 0)
    print(f'{path}: t_end {t_end:.2f} s, quiet window {rms_db(quiet):.1f} dBFS, after rhythm off {rms_db(back):.1f}, '
          f'marker 388Hz {mk[FM]:.1f} / 777Hz {mk[2 * FM]:.1f} dBFS (floor {nq_m[FM]:.1f} / {nq_m[2 * FM]:.1f}), '
          f'clipped in windows {clip}, valid {valid}')
    print(f'  quiet window lines: 440Hz {nq[F]:.1f} dBFS, 880Hz {nq[2 * F]:.1f} dBFS')
    for r in rows:
        print(r)
    return valid, res


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    takes = []
    for p in sys.argv[1:]:
        valid, res = take(p)
        if valid:
            takes.append(res)
    print(f'valid takes: {len(takes)} of {len(sys.argv) - 1}')
    for c in range(9):
        out = []
        for name in ('mod', 'car'):
            vs = [r[(c, name)] for r in takes]
            out.append(f'{name}: ' + (vs[0] if vs and all(x == vs[0] for x in vs) else 'undecided'))
        print(f'ch{c}: ' + ', '.join(out))


if __name__ == '__main__':
    main()
