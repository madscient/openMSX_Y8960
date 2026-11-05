#!/usr/bin/env python3
"""opl2-panpot.tcl が書き出した WAV を判定する。

  python check-opl2-panpot.py <WAV のあるディレクトリ>

定位が効いていなければ *_left / *_right も center と同じ L=R になる。
BD はキャリアを 6dB 下げて鳴らすので、リズム音を 2 倍で出していれば bd_left が ch7_left と同じ大きさ、
1 : 1 なら半分になる。
そこが判別力のある部分である。
"""
import struct
import sys
import wave

NAMES = ("fm_center", "fm_left", "fm_right", "ch7_left", "bd_left",
         "adpcm_center", "adpcm_left")


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
    got = {name: peaks(f"{directory}/{name}.wav") for name in NAMES}
    for name, (l, r) in got.items():
        print(f"{name:12s} L_peak={l:6d} R_peak={r:6d}")

    failures = []
    for name in ("fm_center", "adpcm_center"):
        if got[name][0] == 0 or got[name][1] == 0:
            failures.append(f"{name} が無音。音が鳴っていない")
        if got[name][0] != got[name][1]:
            failures.append(f"{name} で L と R が違う")
    for name in ("fm_left", "ch7_left", "bd_left", "adpcm_left"):
        if got[name][0] == 0 or got[name][1] != 0:
            failures.append(f"{name} が左に振り切れていない")
    if got["fm_right"][1] == 0 or got["fm_right"][0] != 0:
        failures.append("fm_right が右に振り切れていない")
    # BD は ch7 のスロットをキャリアだけ 6dB 下げて使う。リズム音がメロディの 2 倍なら同じ大きさ
    want = got["ch7_left"][0]
    if abs(got["bd_left"][0] - want) > want * 0.03 + 2:
        failures.append(f"bd_left が ch7_left と同じ大きさでない。リズム音が 2 倍になっていない (want {want})")

    if failures:
        for f in failures:
            print("NG:", f)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
