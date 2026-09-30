#!/usr/bin/env python3
"""prescale.tcl が書き出した WAV の音程を判定する。

  python check-prescale.py <WAV のあるディレクトリ>

各区間の周波数を、直流分を引いたあとのゼロ交差の数から求める。
期待値との差が 1% 以内なら OK。レートの切り替えが効いていなければ、
音程は期待値の整数倍か整数分の 1 にずれる。
"""
import glob
import os
import struct
import sys
import wave

EXPECTED = {"p6": 8e6 / 4 / 16 / 128, "p3": 8e6 / 2 / 16 / 128, "p2": 8e6 / 16 / 128}


def frequency(path):
    with wave.open(path, "rb") as w:
        ch, rate, n = w.getnchannels(), w.getframerate(), w.getnframes()
        data = w.readframes(n)
    samples = struct.unpack("<%dh" % (len(data) // 2), data)[::ch]
    # skip the first 50 ms: the switch itself may drop or repeat samples
    samples = samples[rate // 20:]
    mean = sum(samples) / len(samples)
    s = [x - mean for x in samples]
    crossings = sum(1 for a, b in zip(s, s[1:]) if (a < 0) != (b < 0))
    return crossings / 2 / (len(s) / rate), max(abs(x) for x in s)


def main():
    d = sys.argv[1]
    ok = True
    for name, want in EXPECTED.items():
        files = glob.glob(os.path.join(d, "makoto-prescale-%s*.wav" % name))
        if len(files) != 1:
            print("NG %s: %d files" % (name, len(files)))
            ok = False
            continue
        got, amp = frequency(files[0])
        good = abs(got - want) / want < 0.01 and amp > 100
        ok &= good
        print("%s %s: %.1f Hz (expect %.1f), amplitude %d"
              % ("OK" if good else "NG", name, got, want, amp))
    print("OK" if ok else "NG")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
