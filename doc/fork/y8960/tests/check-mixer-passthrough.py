#!/usr/bin/env python3
"""mixer-passthrough.tcl が書き出した WAV を判定する。

  python check-mixer-passthrough.py <WAV のあるディレクトリ>

ミキサーが素通りなら、B6h-B7h に何を書いても音量は変わらない。
判別力があるのはそこで、レジスタから音量を作っていた頃は
全レジスタに 0 を書くと after のピークが 1/16 に落ちた。

**厳密な一致は求めない。** openMSX のミキサーが直流分を落とす過渡が
2 つのキャプチャにまたがって残り、数 % の差が出る。捕まえたいのは
94% の落ち込みなので、5% の許容で十分に判別できる。
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
    before = peak(f"{d}/before.wav")
    after = peak(f"{d}/after.wav")
    print(f"before peak={before}  after peak={after}")

    ok = True
    if before < 1000:
        print("NG: before が無音に近い。音が出ていないので何も判定できない")
        ok = False
    TOLERANCE = 0.05
    if abs(after - before) > before * TOLERANCE:
        print(f"NG: ミキサーのレジスタを書いたら音量が {abs(after - before) / before:.0%} "
              "変わった。素通りになっていない")
        ok = False
    print("OK" if ok else "NG")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
