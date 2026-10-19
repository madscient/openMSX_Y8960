#!/usr/bin/env python3
"""scc-panpot.tcl が書き出した WAV と scc-panpot.txt を判定する。

  python check-scc-panpot.py <出力のあるディレクトリ>

定位が効いていなければ left/right も center と同じ L=R になる。
chB_left は番地とチャンネルの対応を、zero は 0 が左端になることを見ている。
"""
import struct
import sys
import wave

CENTRE_GAIN = 0.7071  # Y8960Pan.hh の中央は両側 1/sqrt(2)


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
    failures = []

    with open(f"{directory}/scc-panpot.txt", encoding="utf-8") as f:
        lines = f.read().splitlines()
    for line in lines:
        if line.startswith("FAIL"):
            print(line)
    if not lines or lines[-1] != "RESULT: ALL PASS":
        failures.append("scc-panpot.txt のレジスタの検査が通っていない")

    got = {name: peaks(f"{directory}/{name}.wav")
           for name in ("center", "left", "right", "zero", "chB_left")}
    for name, (l, r) in got.items():
        print(f"{name:8s} L_peak={l:6d} R_peak={r:6d}")

    if got["center"][0] == 0 or got["center"][1] == 0:
        failures.append("center が無音。音が鳴っていない")
    if got["center"][0] != got["center"][1]:
        failures.append("center で L と R が違う")
    if got["left"][0] >= 32767:
        failures.append("left がクリップしている。中央との比が測れない")
    for name in ("left", "zero", "chB_left"):
        if got[name][0] == 0 or got[name][1] != 0:
            failures.append(f"{name} が左に振り切れていない")
    if got["right"][1] == 0 or got["right"][0] != 0:
        failures.append("right が右に振り切れていない")
    want = got["left"][0] * CENTRE_GAIN
    if abs(got["center"][0] - want) > want * 0.03 + 2:
        failures.append(f"center が left の 1/sqrt(2) でない (want {want:.0f})")

    if failures:
        for f in failures:
            print("NG:", f)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
