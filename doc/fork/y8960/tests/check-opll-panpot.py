#!/usr/bin/env python3
"""opll-panpot.tcl が書き出した WAV を判定する。

  python check-opll-panpot.py <WAV のあるディレクトリ>

定位が効いていなければ left/right/bd_left も center と同じ L=R になる。
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
           for name in ("center", "zero", "left", "right", "bd_left")}
    for name, (l, r) in got.items():
        print(f"{name:8s} L_peak={l:6d} R_peak={r:6d}")

    failures = []
    if got["center"][0] == 0 or got["center"][1] == 0:
        failures.append("center が無音。音が鳴っていない")
    if got["center"][0] != got["center"][1]:
        failures.append("center で L と R が違う")
    # 0 は仕様に無く、RTL の定位の表と同じく 1 と同じ左端として扱う
    if got["zero"] != got["left"]:
        failures.append("zero が left と同じでない。0 が左端になっていない")
    if got["left"][0] == 0 or got["left"][1] != 0:
        failures.append("left が左に振り切れていない")
    if got["right"][1] == 0 or got["right"][0] != 0:
        failures.append("right が右に振り切れていない")
    if got["bd_left"][0] == 0 or got["bd_left"][1] != 0:
        failures.append("bd_left が左に振り切れていない。BD が ch7 の定位に従っていない")
    # コアはリズム音を 2 倍で出し、そのままだと 16bit を超えて 32768 で張り付く。
    # ラッパーが 1:1 に戻していれば収まる
    if got["bd_left"][0] >= 32767:
        failures.append("bd_left がクリップしている。リズム音が 2 倍のまま")

    if failures:
        for f in failures:
            print("NG:", f)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
