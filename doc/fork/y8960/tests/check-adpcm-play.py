#!/usr/bin/env python3
"""adpcm-play.tcl が書き出した WAV を判定する。

  python check-adpcm-play.py <WAV のあるディレクトリ>

判別力は 2 つある。

- **2 本の対比**。playing が鳴っていて stopped が無音なら、その音が ADPCM から
  出たものだと言える。playing だけでは、別の音源が鳴っているだけかもしれない
- **基本周波数**。書いた波形は 1 周期 64 ニブルで、DELTA-N が 8000h なので
  49716 * 0.5 / 64 = 388.4Hz になる。これが合っていれば、メモリへの書き込み、
  アドレスの設定、読み出しの速さのどれもが効いていることになる
"""
import struct
import sys
import wave


EXPECTED_HZ = 49716 * 0.5 / 64
TOLERANCE = 0.05


def analyse(path):
    """ピークと、ゼロ交差から求めた基本周波数を返す。"""
    with wave.open(path, "rb") as w:
        rate, channels, frames = w.getframerate(), w.getnchannels(), w.getnframes()
        data = w.readframes(frames)
    samples = struct.unpack("<%dh" % (len(data) // 2), data)
    mono = samples[0::channels]
    if not mono:
        return 0, 0.0
    mean = sum(mono) / len(mono)
    crossings = sum(1 for a, b in zip(mono, mono[1:])
                    if (a - mean) < 0 <= (b - mean))
    return max(map(abs, mono)), crossings / (frames / rate)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    d = sys.argv[1]
    playing, hz = analyse(f"{d}/playing.wav")
    stopped, _ = analyse(f"{d}/stopped.wav")
    print(f"playing peak={playing} {hz:.1f}Hz (expect {EXPECTED_HZ:.1f}Hz)"
          f"  stopped peak={stopped}")

    ok = True
    if playing < 1000:
        print("NG: 再生中に音が出ていない")
        ok = False
    if stopped > playing / 10:
        print("NG: 止めたのに音が残っている。playing の音は ADPCM 由来ではない")
        ok = False
    if abs(hz - EXPECTED_HZ) > EXPECTED_HZ * TOLERANCE:
        print(f"NG: 基本周波数が {hz / EXPECTED_HZ:.2f} 倍ずれている。"
              "書いた波形が意図した速さで読まれていない")
        ok = False
    print("OK" if ok else "NG")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
