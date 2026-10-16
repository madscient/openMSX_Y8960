#!/usr/bin/env python3
"""ssgs-panpot.tcl が書き出した WAV を判定する。

  python check-ssgs-panpot.py <WAV のあるディレクトリ>

定位が効いていなければ left/right も center と同じ L=R になり、
音量が効いていなければ half は center と同じ大きさになる。
そこが判別力のある部分である。
"""
import struct
import sys
import wave


def peaks(path):
    with wave.open(path, "rb") as w:
        assert w.getnchannels() == 2, "ステレオで録れているはず"
        assert w.getsampwidth() == 2, "16bit PCM を想定している"
        data = w.readframes(w.getnframes())
    samples = struct.unpack("<%dh" % (len(data) // 2), data)
    left, right = samples[0::2], samples[1::2]
    peak = lambda xs: max(max(xs), -min(xs))
    return peak(left), peak(right)


def main(directory):
    got = {name: peaks(f"{directory}/{name}.wav")
           for name in ("center", "left", "right", "half", "unit1")}
    for name, (l, r) in got.items():
        print(f"{name:7s} L_peak={l:6d} R_peak={r:6d}")

    failures = []
    if got["center"][0] == 0 or got["center"][1] == 0:
        failures.append("center が無音。音が鳴っていない")
    if got["center"][0] != got["center"][1]:
        failures.append("center で L と R が違う")
    if got["center"][0] >= 32767:
        failures.append("center がクリップしている。half の比較ができない")
    if got["left"][0] == 0 or got["left"][1] != 0:
        failures.append("left が左に振り切れていない")
    if got["right"][1] == 0 or got["right"][0] != 0:
        failures.append("right が右に振り切れていない")
    # 音量 64 は 128 の半分。16bit への丸めと直流分の除去で数 LSB はずれる
    want = got["center"][0] / 2
    if abs(got["half"][0] - want) > want * 0.03 + 2:
        failures.append(f"half が center の半分でない (want {want:.0f})")
    if got["unit1"][0] == 0 and got["unit1"][1] == 0:
        failures.append("unit1 が無音。SSG 系統 1 が鳴っていない")

    if failures:
        for f in failures:
            print("NG:", f)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
