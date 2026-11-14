"""anaform.py の判別力を見るための、作り方ごとの合成の録音を作る。

    py synthform.py <出力先> [乱数の種] [クロックのずれ ppm]

form_nuked.wav、form_ymf262.wav、form_y8950.wav を書く。打は rhymodel.HITS を模型でチップのレートに作り、48kHz に直す。
録音の頭のクリック、ときどき 1.3 秒ほどに延びる歩、打ごとの大きさの揺らぎ（±0.5dB）、50Hz の倍音のうなり、8kHz の細い線、
14kHz の 1 次の高域の落ちを含む。
"""
import sys
import wave
from pathlib import Path

import numpy as np

import rhymodel as M

RATE = 48000


def resample(x, rin):
    nout = int(round(len(x) * RATE / rin))
    X = np.fft.rfft(x)
    Y = np.zeros(nout // 2 + 1, dtype=complex)
    k = min(len(X), len(Y))
    Y[:k] = X[:k]
    return np.fft.irfft(Y, n=nout) * nout / len(x)


def make(path, form, rng, ppm):
    rin = M.CHIP_RATE * (1 + ppm * 1e-6)
    total = int((4.5 + len(M.HITS) * 1.022 + 1.5) * RATE)
    y = rng.standard_normal(total) * 10 ** (-80 / 20)
    t = np.arange(total) / RATE
    for h in range(1, 8):
        y += 10 ** (-70 / 20) / h * np.sin(2 * np.pi * 50 * h * t + h)
    y += 10 ** (-75 / 20) * np.sin(2 * np.pi * 8000 * t)
    y[int(0.3 * RATE):int(0.3 * RATE) + 40] += 0.05
    pos = int(4.5 * RATE)
    nchip = int(0.8 * rin)
    env = np.ones(nchip)
    a, r = int(0.002 * rin), int(0.005 * rin)
    env[:a] = np.linspace(0, 1, a)
    env[-r:] = np.linspace(1, 0, r)
    for i, hit in enumerate(M.HITS):
        if i == 7:
            pos += int(0.33 * RATE)
        x = M.render(form, hit[0], M.regs_of(hit), nchip) * env
        z = resample(x, rin)
        g = 0.2 * 10 ** (rng.uniform(-0.5, 0.5) / 20)
        y[pos:pos + len(z)] += g * z
        pos += int(1.022 * RATE)
    Y = np.fft.rfft(y)
    f = np.fft.rfftfreq(len(y), 1 / RATE)
    y = np.fft.irfft(Y / (1 + 1j * f / 14000), n=len(y))
    s = np.clip(np.round(np.stack([y, y], axis=1) * 32767), -32768, 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(s.tobytes())


def main():
    out = Path(sys.argv[1])
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    ppm = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    for form in M.FORMS:
        make(out / f'form_{form}.wav', form, rng, ppm)
        print(out / f'form_{form}.wav')


if __name__ == '__main__':
    main()
