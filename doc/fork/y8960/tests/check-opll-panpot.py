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
    for name in ("center", "zero"):
        if got[name][0] == 0 or got[name][1] == 0:
            failures.append(f"{name} が無音。音が鳴っていない")
        if got[name][0] != got[name][1]:
            failures.append(f"{name} で L と R が違う")
    if got["left"][0] == 0 or got["left"][1] != 0:
        failures.append("left が左に振り切れていない")
    if got["right"][1] == 0 or got["right"][0] != 0:
        failures.append("right が右に振り切れていない")
    if got["bd_left"][0] == 0 or got["bd_left"][1] != 0:
        failures.append("bd_left が左に振り切れていない。BD が ch7 の定位に従っていない")

    if failures:
        for f in failures:
            print("NG:", f)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
