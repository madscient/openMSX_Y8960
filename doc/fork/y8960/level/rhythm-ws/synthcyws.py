"""mkcyws.py の打の合成の録音を書く。anacyws.py の判別力を見るためのもの。

    py synthcyws.py <出力先> [乱数の種]

書くもの（48kHz、16 ビット、ステレオ）: cy080-tau{1,30,300}.wav、cy100-tau{1,30,300}.wav と、鍵の操作だけで小さな音
（雑音の最大より 10dB）が出るものを足した cy080-art.wav、cy100-art.wav。
CY は rhymodel の nuked の rmXor から作り、080h なら波形 0 で ±0.707、波形 2・3 で 0.707、100h なら波形 0 で ±1、
波形 2 で 1、波形 3 で 0。SD の波形 3 は 0。交流の結合は一次の高域通過（時定数 tau ms。実物の録音の一瞬の音は 2ms ほどで
消えたので 1ms を含める）。床は -56dBFS の雑音と -55dBFS の 50Hz のうなりに、0.3 秒おきほどの突発の音（雑音の最大より
最大 8dB）を混ぜる（実物の録音の床は約 -52dBFS で、ときどき突発の音があった）。大きさは TL 0 の実物の CY-w0 の RMS
（約 -12dBFS）に合わせる。歩は名目 2000ms に、ときどき 1.0-1.37 倍の延びを入れる。頭に 4 秒の無音。
"""
import sys
import wave
from pathlib import Path

import numpy as np

import mkcyws as K
import rhymodel as M

RATE = 48000
GAIN = 10 ** (-6 / 20)


def rmxor(n):
    hh = M.phases(*M.F7, 1, n)
    tc = M.phases(*M.F8, 1, n)
    b = lambda p, k: (p >> k) & 1
    return (b(hh, 2) ^ b(hh, 7)) | (b(hh, 3) ^ b(tc, 5)) | (b(tc, 3) ^ b(tc, 5))


def hit_signal(form, snd, ws, n_chip):
    if snd == 'SD':
        return np.zeros(n_chip)
    x = rmxor(n_chip)
    a = 0.70710678 if form == '080' else 1.0
    if ws == 0:
        return np.where(x == 1, -a, a)
    if ws == 2:
        return np.full(n_chip, a)
    return np.full(n_chip, a if form == '080' else 0.0)


def render(form, tau_ms, art, rng):
    total = int(4.0 * RATE) + int(len(K.hits()) * 2.8 * RATE) + RATE
    y = np.zeros(total)
    t = 4.0
    for k, (name, snd, ws, r) in enumerate(K.hits()):
        n_out = int(K.NOTE_MS / 1000 * RATE)
        n_chip = int(K.NOTE_MS / 1000 * M.CHIP_RATE)
        sig = hit_signal(form, snd, ws, n_chip)
        sig = np.interp(np.arange(n_out) / RATE, np.arange(n_chip) / M.CHIP_RATE, sig)
        a = int(t * RATE)
        y[a:a + n_out] += GAIN * sig
        if art:
            for edge in (a, a + n_out):
                y[edge:edge + 48] += 10 ** (-32 / 20) * np.hanning(48)
        step = 2.0 * (rng.choice([1.0, 1.0, 1.0, 1.05, 1.17, 1.37]))
        t += step
    # 一次の高域通過
    dt = 1 / RATE
    c = (tau_ms / 1000) / (tau_ms / 1000 + dt)
    out = np.zeros_like(y)
    prev_x = prev_y = 0.0
    for i in range(len(y)):
        prev_y = c * (prev_y + y[i] - prev_x)
        prev_x = y[i]
        out[i] = prev_y
    n = np.arange(len(out))
    out += 10 ** (-56 / 20) * rng.standard_normal(len(out))
    out += 10 ** (-55 / 20) * np.sqrt(2) * np.sin(2 * np.pi * 50 * n / RATE)
    for b in range(int(RATE * 0.5), len(out) - RATE, int(RATE * 0.3)):
        pos = b + int(rng.integers(0, RATE // 10))
        out[pos:pos + 96] += 10 ** ((-42 + rng.uniform(0, 8)) / 20) * np.hanning(96) * rng.choice([-1, 1])
    return out


def write(path, x):
    s = np.clip(np.round(x * 32767), -32768, 32767).astype('<i2')
    st = np.repeat(s[:, None], 2, axis=1).reshape(-1)
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(st.tobytes())


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    rng = np.random.default_rng(seed)
    for form in ('080', '100'):
        for tau in (1, 30, 300):
            write(out / f'cy{form}-tau{tau}.wav', render(form, tau, False, rng))
        write(out / f'cy{form}-art.wav', render(form, 1, True, rng))
    print(f'wrote 8 files to {out}')


if __name__ == '__main__':
    main()
