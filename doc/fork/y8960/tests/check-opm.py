#!/usr/bin/env python3
"""opm.tcl が書き出した WAV と opm.txt を判定する。

  python check-opm.py <出力のあるディレクトリ>

closed_note は無音、mmio_note と io_note は左右に同じだけ鳴り、left_only は
右が無音。mix_half は mix_full の半分、mix_mute は無音、mix_others は
mix_full と同じ。

mix_* は最終ミックスで、ミキサーが直流分を落とす過渡が残るので数 % の差を許す。
"""
import struct
import sys
import wave

SILENT = 16        # これ以下なら無音とみなす
LOUD = 1000        # これ以上なら鳴っているとみなす
TOLERANCE = 0.05


def peaks(path):
    with wave.open(path, "rb") as w:
        assert w.getnchannels() == 2, "ステレオで録れているはず"
        assert w.getsampwidth() == 2, "16bit PCM を想定している"
        data = w.readframes(w.getnframes())
    samples = struct.unpack("<%dh" % (len(data) // 2), data)
    left, right = samples[0::2], samples[1::2]
    peak = lambda xs: max(max(xs, default=0), -min(xs, default=0))
    return peak(left), peak(right)


def main(directory):
    failures = []

    with open(f"{directory}/opm.txt", encoding="utf-8") as f:
        lines = f.read().splitlines()
    for line in lines:
        if line.startswith("FAIL"):
            print(line)
    if not lines or lines[-1] != "RESULT: ALL PASS":
        failures.append("opm.txt のレジスタの検査が通っていない")

    names = ("closed_note", "mmio_note", "io_note", "left_only",
             "mix_full", "mix_half", "mix_mute", "mix_others")
    got = {name: peaks(f"{directory}/{name}.wav") for name in names}
    for name, (l, r) in got.items():
        print(f"{name:12s} L_peak={l:6d} R_peak={r:6d}")

    l, r = got["closed_note"]
    if l > SILENT or r > SILENT:
        failures.append("closed_note が鳴っている。閉じたポートへの書き込みが届いた")
    for name in ("mmio_note", "io_note"):
        l, r = got[name]
        if l < LOUD or r < LOUD:
            failures.append(f"{name} が鳴っていない")
        elif l != r:
            failures.append(f"{name} で L と R が違う")
    l, r = got["left_only"]
    if l < LOUD or r > SILENT:
        failures.append("left_only が左だけに出ていない")

    base = got["mix_full"][0]
    if base < LOUD:
        failures.append("mix_full が無音に近い。ミキサーの判定ができない")
    else:
        def near(name, want):
            for side, value in zip("LR", got[name]):
                if abs(value - want) > base * TOLERANCE:
                    failures.append(f"{name} の {side} が {want:.0f} 付近でない")
        near("mix_full", base)
        near("mix_half", base * 64 / 128)
        near("mix_mute", 0)
        near("mix_others", base)

    if failures:
        for f in failures:
            print("NG:", f)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
