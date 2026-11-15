"""anabd.py の判別力を見るための合成の録音を作る。電源投入の音、ときどき延びる歩、電源のうなり、経路のひずみと
周波数特性、クロックのずれ、打ごとの大きさの揺らぎを含む。

    py synthbd.py <出力先のディレクトリ> [乱数の種] [クロックのずれ ppm] [FM の深さ rad]

ファイル名は BD CON1 の作り方（CON0 はどれも FM。bd_old だけ CON0 がキャリアだけ）:
  bd_carrier.wav : キャリアだけ
  bd_fm.wav      : CON によらず FM
  bd_carmod.wav  : キャリアと変調器（FM なし）
  bd_fmmod.wav   : FM と変調器
  bd_old.wav     : CON0 はキャリアだけ、CON1 はキャリアと変調器
  ctl_bad.wav    : 対照の CTL CON1 が FM になっている（回は無効になるはず）。BD CON1 はキャリアだけ
"""
import sys
import wave
from pathlib import Path

import numpy as np

from mkbd import SEQ, BLOCK, FNUM

RATE = 48000
args = sys.argv[1:]
SEED = int(args[1]) if len(args) > 1 else 5
PPM = float(args[2]) if len(args) > 2 else 0.0
INDEX = float(args[3]) if len(args) > 3 else 1.6
F = FNUM * 3579545 / 72 * 2 ** (BLOCK - 1) / 2 ** 19 * (1 + PPM * 1e-6)
rng = np.random.default_rng(SEED)


def tone(n, form, amp):
    t = np.arange(n) / RATE
    fm = INDEX * (1 + rng.normal(0, 0.05)) if form in ('FM', 'FM + modulator') else 0.0
    x = np.sin(2 * np.pi * 2 * F * t + fm * np.sin(2 * np.pi * 3 * F * t))
    if form in ('carrier + modulator', 'FM + modulator'):
        x = x + 10 ** (-12 / 20) * np.sin(2 * np.pi * 3 * F * t)
    env = np.minimum(1, t / 0.003)
    rel = int(0.8 * RATE)
    env[rel:] *= np.exp(-(t[rel:] - 0.8) / 0.03)
    return amp * 10 ** (rng.normal(0, 0.3) / 20) * x * env


def path_response(y):
    sp = np.fft.rfft(y)
    fr = np.fft.rfftfreq(len(y), 1 / RATE)
    # 低域の切り（20Hz）と、高域へのなだらかな落ち、1kHz 付近の小さな山
    h = (fr / 20) / np.sqrt(1 + (fr / 20) ** 2) * 10 ** (-1.5 * np.log2(np.maximum(fr, 50) / 1000) / 20)
    h *= 1 + 0.15 * np.exp(-((fr - 1000) / 300) ** 2)
    return np.fft.irfft(sp * h, len(y))


def make(path, ctl1, bd0, bd1):
    forms = {('CTL', 0): 'FM', ('CTL', 1): ctl1, ('BD', 0): bd0, ('BD', 1): bd1}
    total = int((8.0 + 17 * 1.05 + 3.0) * RATE)
    y = rng.standard_normal(total) * 10 ** (-86 / 20)
    p = int(2.0 * RATE)
    y[p:] += rng.standard_normal(total - p) * 10 ** (-68 / 20)
    t = np.arange(total) / RATE
    for k in range(1, 25):
        y += 10 ** ((-74 - 2 * k) / 20) * np.sin(2 * np.pi * 50 * k * t + rng.uniform(0, 6.3))
    for tp, lv, ln in ((2.0, -38, 0.035), (2.2, -18, 0.23), (2.6, -44, 0.03), (3.0, -40, 0.05), (3.4, -45, 0.03)):
        q = int(tp * RATE)
        y[q:q + int(ln * RATE)] += rng.standard_normal(int(ln * RATE)) * 10 ** (lv / 20)
    pos = int(7.5 * RATE)
    n = int(0.95 * RATE)
    for i, key in enumerate(SEQ):
        if i == 7:
            pos += int(0.35 * RATE)
        amp = 0.08 if key[0] == 'CTL' else 0.16
        y[pos:pos + n] += tone(n, forms[key], amp)
        pos += int(1.03 * RATE)
    y = path_response(y)
    y = y + 0.05 * y ** 2 + 0.02 * y ** 3
    s = np.clip(np.round(np.stack([y, y], axis=1) * 32767), -32768, 32767).astype('<i2')
    with wave.open(str(path), 'wb') as wv:
        wv.setnchannels(2)
        wv.setsampwidth(2)
        wv.setframerate(RATE)
        wv.writeframes(s.tobytes())


out = Path(args[0])
out.mkdir(parents=True, exist_ok=True)
CM = 'carrier + modulator'
make(out / 'bd_carrier.wav', CM, 'FM', 'carrier only')
make(out / 'bd_fm.wav', CM, 'FM', 'FM')
make(out / 'bd_carmod.wav', CM, 'FM', CM)
make(out / 'bd_fmmod.wav', CM, 'FM', 'FM + modulator')
make(out / 'bd_old.wav', CM, 'carrier only', CM)
make(out / 'ctl_bad.wav', 'FM', 'FM', 'carrier only')
print(f'written (seed {SEED}, {PPM:+.0f} ppm, FM depth {INDEX} rad, f {F:.3f} Hz)')
