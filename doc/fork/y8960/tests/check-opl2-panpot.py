#!/usr/bin/env python3
"""opl2-panpot.tcl が書き出した WAV を判定する。

  python check-opl2-panpot.py <WAV のあるディレクトリ>

定位が効いていなければ *_left / *_right も center と同じ L=R になり、
ADPCM の音量が効いていなければ adpcm_half が adpcm_center と同じ大きさになる。
そこが判別力のある部分である。
"""
import struct
import sys
import wave

NAMES = ("fm_center", "fm_left", "fm_right", "bd_left",
         "adpcm_center", "adpcm_left", "adpcm_half")


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
    for name in ("fm_left", "bd_left", "adpcm_left"):
        if got[name][0] == 0 or got[name][1] != 0:
            failures.append(f"{name} が左に振り切れていない")
    if got["fm_right"][1] == 0 or got["fm_right"][0] != 0:
        failures.append("fm_right が右に振り切れていない")
    # 音量 64 は最大 128 の 0.5 倍。16bit への丸めで数 LSB はずれる
    want = got["adpcm_center"][0] * 64 / 128
    if abs(got["adpcm_half"][0] - want) > want * 0.03 + 2:
        failures.append(f"adpcm_half が adpcm_center の半分でない (want {want:.0f})")

    if failures:
        for f in failures:
            print("NG:", f)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
