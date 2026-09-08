#!/usr/bin/env python3
"""opl2-waveform.tcl が書き出した ws0.wav / ws2.wav を判定する。

  python check-opl2-waveform.py <ws0.wav と ws2.wav のあるディレクトリ>

WS0 は全波サイン、WS2 は絶対値サイン。判別力があるのは WS2 に負のサンプルが
無いことで、波形選択が効いていなければ WS0 と同じ波形になり負が半分出る。
"""
import struct
import sys
import wave


def load(path):
    with wave.open(path, "rb") as w:
        assert w.getsampwidth() == 2, "16bit PCM を想定している"
        channels = w.getnchannels()
        data = w.readframes(w.getnframes())
    samples = struct.unpack("<%dh" % (len(data) // 2), data)
    return samples[::channels]  # 左チャンネルだけ見れば足りる


def main(directory):
    ws0 = load(f"{directory}/ws0.wav")
    ws2 = load(f"{directory}/ws2.wav")

    failures = []
    if ws0 == ws2:
        failures.append("WS0 と WS2 が同一。波形選択が効いていない")

    nonzero0 = [s for s in ws0 if s]
    nonzero2 = [s for s in ws2 if s]
    if not nonzero0 or not nonzero2:
        failures.append("録音が無音。ノートが鳴っていない")
    else:
        negative0 = sum(1 for s in nonzero0 if s < 0) / len(nonzero0)
        negative2 = sum(1 for s in nonzero2 if s < 0) / len(nonzero2)
        print(f"WS0 (full sine): min={min(ws0)} max={max(ws0)} 負={negative0:.1%}")
        print(f"WS2 (abs sine) : min={min(ws2)} max={max(ws2)} 負={negative2:.1%}")
        if negative0 < 0.4:
            failures.append(f"WS0 に負のサンプルがほとんど無い ({negative0:.1%})")
        if negative2 > 0.0:
            failures.append(f"WS2 に負のサンプルがある ({negative2:.1%})")

    if failures:
        for f in failures:
            print("NG:", f)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
