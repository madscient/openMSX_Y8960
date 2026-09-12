#!/usr/bin/env python3
"""mixer-remove.tcl が書き出した WAV を判定する。

  python check-mixer-remove.py <WAV のあるディレクトリ>

判別力があるのは 2 本の対比である。抜く前が無音で抜いた後が鳴っていれば、
鳴っているのは抜いたことの結果だと言える。restored だけでは、そもそも
切り替えが効いていなかっただけかもしれない。
"""
import struct
import sys
import wave

LOUD, SILENT = "鳴っている", "無音"

EXPECTED = [
    ("muted",    SILENT, "y8960 を選んでいる間の本体 PSG"),
    ("restored", LOUD,   "カートリッジを抜いたあとの本体 PSG"),
]


def peak(path):
    with wave.open(path, "rb") as w:
        data = w.readframes(w.getnframes())
    samples = struct.unpack("<%dh" % (len(data) // 2), data)
    return max((abs(s) for s in samples), default=0)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    d = sys.argv[1]
    peaks = {name: peak(f"{d}/{name}.wav") for name, _, _ in EXPECTED}

    threshold = peaks["restored"] / 10

    ok = True
    for name, want, what in EXPECTED:
        got = LOUD if peaks[name] > threshold else SILENT
        mark = "OK" if got == want else "NG"
        if got != want:
            ok = False
        print(f"  {mark} {name:9s} peak={peaks[name]:6d}  {what} -> {want}")

    if peaks["restored"] < 1000:
        print("NG: 抜いたあとが小さすぎる。音が出ていないので判定できない")
        ok = False

    print("OK" if ok else "NG")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
