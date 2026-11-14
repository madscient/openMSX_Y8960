"""mkcon.py のパッチを鳴らした録音を測る。

    py anacon.py take1.wav [...]

位置合わせ: 立ち上がり（anaws.find_attacks）を、[t+10ms, t+110ms] の 2kHz 以上の割合で TT（低い）と HH（高い）に分ける。
TT の目印は 9 個。HH の打 1-8 は、前の TT の 0.9-1.45 秒後の HH の立ち上がり、無ければ前後の TT の中点。
HH の打 0 は、最初の TT の 0.9-1.45 秒前の HH の立ち上がり、無ければ最初の TT から TT の間隔の半分だけ前。
測る値: [onset+10ms, onset+410ms] の 2-16kHz の RMS（dBFS）。

判定の基準（録音を見る前に決めた）:
  - どの回でも、C7h=01h の HH のどの打も、C7h=00h の HH（打 2-16 の 4 打）のどの打より 20dB 以上大きい: 「CON が HH を消す」
  - どの回でも、2 つの組の平均の差が 3dB 以内で、C7h=00h の打がすべて床より 20dB 以上大きい: 「CON に関わらない」
  - ほかは「決まらない」
  - 回が有効なのは、TT の目印が 9 個そろったときだけ
  - 打 0 は別に報告する。lead の床（最初の TT の 2.6 秒前）より 20dB 以上大きければ「鳴る」、6dB 以内なら「鳴らない」
"""
import sys

import numpy as np

import anaws

C7_SEQ = [0x00, 0x01] * 4
WIN = (0.010, 0.410)
HF = (2000.0, 16000.0)


def hf_rms(seg, rate):
    # リズム音は持続を持たず、鍵を押している間も RR で減る。窓全体に 1 枚のハン窓を掛けると頭の電力を削るので、
    # 10ms の枠ごとにハン窓で測って平均する
    seg = seg - seg.mean()
    f = int(0.010 * rate)
    k = len(seg) // f
    w = np.hanning(f)
    sp = np.fft.rfft(seg[:k * f].reshape(k, f) * w, axis=1)
    fr = np.fft.rfftfreq(f, 1 / rate)
    sel = (fr >= HF[0]) & (fr < HF[1])
    p = 2 * np.sum(np.abs(sp[:, sel]) ** 2) / (k * f * np.sum(w ** 2))
    return 10 * np.log10(max(p, 1e-14))


def hf_frac(m, rate, t):
    seg = m[int((t + 0.010) * rate):int((t + 0.110) * rate)]
    seg = seg - seg.mean()
    sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2
    fr = np.fft.rfftfreq(len(seg), 1 / rate)
    tot = sp[fr >= 20].sum()
    return float(sp[fr >= HF[0]].sum() / tot) if tot > 0 else 0.0


def measure(m, rate, t):
    return hf_rms(m[int((t + WIN[0]) * rate):int((t + WIN[1]) * rate)], rate)


def analyse(path):
    m, rate, clip = anaws.read(path)
    db = anaws.frames_db(m, rate)
    floor0 = float(np.median(db[: int(1.0 / anaws.FRAME)]))
    attacks = anaws.find_attacks(db, floor0 + 20)
    kinds = [(t, hf_frac(m, rate, t)) for t in attacks]
    tts_all = [t for t, f in kinds if f < 0.2]
    hhs = [t for t, f in kinds if f >= 0.5]
    # 目印の TT は、2-2.9 秒おきに 9 個並ぶ。電源投入の音が低い音に分けられても、この並びには乗らない
    best = []
    for i, s in enumerate(tts_all):
        chain = [s]
        for t in tts_all[i + 1:]:
            if 1.8 <= t - chain[-1] <= 2.9:
                chain.append(t)
            elif t - chain[-1] > 2.9:
                break
        if len(chain) > len(best):
            best = chain
    # 試験は TT で終わる。電源投入の低い音が最初の TT の約 2 秒前にあると並びの頭に付くので、後ろの 9 個を取る
    tts = best[-9:]
    res = {'path': path, 'clip': clip, 'floor0': floor0, 'n_tt': len(best), 'valid': len(best) >= 9}
    if not res['valid']:
        res['tts'] = tts
        return res
    half = float(np.median(np.diff(tts))) / 2
    res['floor_hf'] = measure(m, rate, tts[0] - 2.6)
    on0 = [t for t in hhs if tts[0] - 1.45 <= t <= tts[0] - 0.9]
    t0 = on0[-1] if on0 else tts[0] - half
    res['hit0'] = (t0, bool(on0), measure(m, rate, t0))
    hits = []
    for k, c7 in enumerate(C7_SEQ):
        a, b = tts[k], tts[k + 1]
        on = [t for t in hhs if a + 0.9 <= t <= a + 1.45]
        t = on[0] if on else (a + b) / 2
        hits.append((c7, t, bool(on), measure(m, rate, t)))
    res['hits'] = hits
    res['tt_steps'] = np.diff(tts)
    return res


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    gate, none_, h0 = [], [], []
    for path in sys.argv[1:]:
        r = analyse(path)
        print(f'{path}: clipped {r["clip"]}, head floor {r["floor0"]:.1f} dBFS, TT anchors {r["n_tt"]}')
        if not r['valid']:
            print('  invalid take (TT anchors < 9):', ' '.join(f'{t:.2f}' for t in r['tts']))
            gate.append(False)
            none_.append(False)
            continue
        print(f'  TT steps {r["tt_steps"].min():.3f}-{r["tt_steps"].max():.3f} s, '
              f'lead floor (2-16kHz) {r["floor_hf"]:.1f} dBFS')
        t0, f0, v0 = r['hit0']
        print(f'  hit 0 (C7h=00h): {v0:6.1f} dB at {t0:.3f} s ({"attack" if f0 else "predicted"})')
        a = [h[3] for h in r['hits'] if h[0] == 0x00]
        b = [h[3] for h in r['hits'] if h[0] == 0x01]
        for c7, t, f, v in r['hits']:
            print(f'    C7h={c7:02X}h {v:6.1f} dB at {t:.3f} s ({"attack" if f else "predicted"})')
        print('  C7h=00h ' + ' '.join(f'{x:6.1f}' for x in a))
        print('  C7h=01h ' + ' '.join(f'{x:6.1f}' for x in b))
        gate.append(min(b) >= max(a) + 20)
        none_.append(abs(np.mean(a) - np.mean(b)) <= 3 and min(a) >= r['floor_hf'] + 20)
        fl = r['floor_hf']
        h0.append('sounds' if v0 >= fl + 20 else 'silent' if v0 <= fl + 6 else 'undecided')
    v = 'CON silences HH' if gate and all(gate) else 'CON does not matter' if none_ and all(none_) else 'undecided'
    print('verdict:', v)
    print('hit 0 per take:', h0)


if __name__ == '__main__':
    main()
