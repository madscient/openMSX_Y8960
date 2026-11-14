"""mkcyws.py のパッチを鳴らした録音を測り、CY の位相の定数が 080h（Nuked-OPL3）か 100h（MAME・ymfm）かを判定する。

    py anacyws.py take1.wav [take2.wav ...]

区間: mkcyws.py の ROUNDS 巡 × 4 打（CY-w0、CY-w3、SD-w3、CY-w2）と最後の目印。名目 2000ms おき（600ms 鳴らして 1400ms 休む）。
目印は CY-w0（鳴る）。直流の一瞬の音と取り違えないよう、目印は差分を取った信号（高域が強まる）の 5ms の枠で探し、
床より 25dB 以上が 300ms 以上続く区間とする。巡の周期 P は次の目印までの間隔の 1/4。
CY-w3・SD-w3・CY-w2 は、目印の立ち上がりから 1P・2P・3P の位置に置き、[位置 - 0.6s, 位置 + 鳴らす長さ + 0.6s]
（目印の終わり + 0.05s より前は使わない）の中の、1ms ごとの最大の絶対値の最大（dBFS）を測る。雑音の基準は、最初の目印の
1.2 秒前から 0.2 秒前までの 1ms ごとの最大の絶対値の最大。

直流の段は、交流の結合で一瞬の音になる。実物の YM3812 と SPFM Light と録音の機器の組では、2ms ほどで消える鋭い音だった。
初めの版は 5ms の枠の RMS の跳ね上がりで測ったが、一瞬の音が枠で薄まり、TL 10h・3 巡の 3 回の録音では基準の上で決まらなかった
（2026-11-15。CY-w2 が床より 16〜26dB）。TL を 0 にし、1ms の最大で測る形に直した。

判定の基準（直した後の録音を見る前に決めた）:
  - CY-w2 が雑音の基準より 15dB 以上大きい巡だけを有効とする（直流の一瞬の音が録音で見えること）
  - CY-w3 と CY-w2 の差が 6dB 以内なら「一瞬の音あり」（080h の予想。波形 2 と 3 は同じ直流 0.707）
  - CY-w3 が CY-w2 より 15dB 以上小さければ「無音」（100h の予想。波形 3 は無音）
  - ほかは「決まらない」
  - 有効な巡がすべて「一瞬の音あり」なら 080h、すべて「無音」なら 100h、ほかは決まらない
  - SD-w3（どちらの定数でも無音の対照）は値を出すだけで、判定には使わない
"""
import sys

import numpy as np

import anaws
import mkcyws as K

NOTE = K.NOTE_MS / 1000
MARK_DB = 25
MARK_MIN = 0.300
VALID_DB = 15
SAME_DB = 6
SILENT_DB = 15
SLACK = 0.60


def markers(dbh, floorh):
    on = dbh > floorh + MARK_DB
    out = []
    i, n = 0, len(on)
    gap = int(0.030 / anaws.FRAME)
    while i < n:
        if not on[i]:
            i += 1
            continue
        j = last = i
        while j < n and (on[j] or j - last <= gap):
            if on[j]:
                last = j
            j += 1
        if (last - i + 1) * anaws.FRAME >= MARK_MIN:
            out.append((i * anaws.FRAME, (last + 1) * anaws.FRAME))
        i = last + 1
    return out


def peak_db(m, rate, t0, t1):
    a, b = max(0, int(t0 * rate)), min(len(m), int(t1 * rate))
    if b <= a:
        return float('nan')
    return float(20 * np.log10(np.abs(m[a:b]).max() + 1e-12))


def analyse(path):
    m, rate, clip = anaws.read(path)
    dbh = anaws.frames_db(np.diff(m, prepend=m[0]), rate)
    floorh = float(np.median(dbh[: int(1.0 / anaws.FRAME)]))
    mk = markers(dbh, floorh)
    print(f'{path}: {rate} Hz, clipped {clip}, {len(mk)} markers (expect {K.ROUNDS + 1})')
    if len(mk) != K.ROUNDS + 1:
        print(f'  WARNING: {len(mk)} markers, expected {K.ROUNDS + 1}; the take is not judged')
        return ['invalid']
    noise = peak_db(m, rate, mk[0][0] - 1.2, mk[0][0] - 0.2)
    print(f'  noise peak {noise:.1f} dBFS')
    results = []
    for k, ((s, e), (s_next, _)) in enumerate(zip(mk, mk[1:])):
        P = (s_next - s) / 4
        v = {}
        for slot, name in ((1, 'CY-w3'), (2, 'SD-w3'), (3, 'CY-w2')):
            t = s + slot * P
            v[name] = peak_db(m, rate, max(t - SLACK, e + 0.05), t + NOTE + SLACK)
        c3, sd, c2 = v['CY-w3'], v['SD-w3'], v['CY-w2']
        if c2 < noise + VALID_DB:
            verdict = 'invalid'
        elif abs(c3 - c2) <= SAME_DB:
            verdict = 'click'
        elif c3 <= c2 - SILENT_DB:
            verdict = 'silent'
        else:
            verdict = '?'
        results.append(verdict)
        print(f'  round {k}: P {P:.3f} s  peak CY-w3 {c3:6.1f}  SD-w3 {sd:6.1f}  CY-w2 {c2:6.1f} dBFS  -> {verdict}')
    return results


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    allv = []
    for p in sys.argv[1:]:
        allv += analyse(p)
    valid = [v for v in allv if v != 'invalid']
    if valid and all(v == 'click' for v in valid):
        d = '080h (Nuked-OPL3)'
    elif valid and all(v == 'silent' for v in valid):
        d = '100h (MAME, ymfm)'
    else:
        d = 'undecided'
    print(f'decision: {d}  (rounds: {" ".join(allv)})')


if __name__ == '__main__':
    main()
