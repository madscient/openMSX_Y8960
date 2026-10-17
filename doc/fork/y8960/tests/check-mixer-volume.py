#!/usr/bin/env python3
"""mixer-volume.tcl が書き出した WAV を判定する。

  python check-mixer-volume.py <WAV のあるディレクトリ>

SSG の音量 (7FF7h) が 128 / 64 / 0 / FFh のときのピークと、他の 3 本を 0 に
したときに SSG が変わらないことを見る。

**厳密な一致は求めない。** openMSX のミキサーが直流分を落とす過渡が
キャプチャにまたがって残り、数 % の差が出る。
"""
import struct
import sys
import wave


def peak(path):
    with wave.open(path, "rb") as w:
        data = w.readframes(w.getnframes())
    samples = struct.unpack("<%dh" % (len(data) // 2), data)
    return max((abs(s) for s in samples), default=0)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    d = sys.argv[1]
    names = ("vol_reset", "vol_half", "vol_mute", "vol_others", "vol_ff")
    got = {n: peak(f"{d}/{n}.wav") for n in names}
    for n in names:
        print(f"{n:11s} peak={got[n]:6d}")

    TOLERANCE = 0.05
    base = got["vol_reset"]
    failures = []
    if base < 1000:
        failures.append("vol_reset が無音に近い。音が出ていないので何も判定できない")
    else:
        def near(name, want):
            if abs(got[name] - want) > base * TOLERANCE:
                failures.append(f"{name} が {want:.0f} 付近でない")
        near("vol_half", base * 64 / 128)
        near("vol_mute", 0)
        near("vol_others", base)
        near("vol_ff", base)
    for f in failures:
        print("NG:", f)
    print("OK" if not failures else "NG")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
