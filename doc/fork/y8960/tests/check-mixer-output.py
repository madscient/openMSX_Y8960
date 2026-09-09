#!/usr/bin/env python3
"""mixer-output.tcl が書き出した WAV を判定する。

  python check-mixer-output.py <WAV のあるディレクトリ>

判別力があるのは無音を期待している 2 本で、切り替えが効いていなければ
そこに音が出る。しきい値は素の音量の 1/10 に取ってある。
"""
import struct
import sys
import wave

LOUD, SILENT = "鳴っている", "無音"

EXPECTED = [
    ("psg_msx",    LOUD,   "本体 PSG だけ鳴らして msx を選んだ"),
    ("psg_y8960",  SILENT, "本体 PSG だけ鳴らして y8960 を選んだ"),
    ("ssgs_y8960", LOUD,   "SSGS だけ鳴らして y8960 を選んだ"),
    ("ssgs_msx",   SILENT, "SSGS だけ鳴らして msx を選んだ"),
    ("both_mix",   LOUD,   "両方鳴らして mix を選んだ"),
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

    loud = [peaks[n] for n, want, _ in EXPECTED if want is LOUD]
    threshold = min(loud) / 10

    ok = True
    for name, want, what in EXPECTED:
        got = LOUD if peaks[name] > threshold else SILENT
        mark = "OK" if got == want else "NG"
        if got != want:
            ok = False
        print(f"  {mark} {name:12s} peak={peaks[name]:6d}  {what} -> {want}")

    if min(loud) < 1000:
        print("NG: 鳴っているはずの側が小さすぎる。音が出ていないので判定できない")
        ok = False

    print("OK" if ok else "NG")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
